"""Regresiones de trazabilidad, edición y garantías de PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest


def test_migrated_schema_matches_models(application):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from app.db.base import Base
    from app.db.session import engine

    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []


@pytest.mark.parametrize("extra", [
    {"creado_por": "usuario_ajeno"},
    {"actualizado_por": "usuario_ajeno"},
    {"estado_multa": "PAGADA"},
])
def test_fine_actor_and_computed_state_cannot_be_submitted(client, multa_data, extra):
    response = client.post("/api/multas", json={**multa_data, **extra})
    assert response.status_code == 422, response.text
    assert client.get("/api/multas").json()["total"] == 0


@pytest.mark.parametrize("value", [None, True, False, {}, [], "1e2", "99999999999.00"])
def test_non_money_values_are_rejected_without_partial_write(client, multa_data, value):
    response = client.post("/api/multas", json={**multa_data, "monto": value})
    assert response.status_code == 422, response.text
    assert client.get("/api/multas").json()["total"] == 0


def test_soft_delete_preserves_record_history_and_code(client, multa_data, pago_data):
    fine = client.post("/api/multas", json=multa_data).json()
    client.post("/api/auth/login", json={"username": "operador_baja", "password": "demo"})
    response = client.request("DELETE", f"/api/multas/{fine['id']}", json={"motivo": "Registro de demostración duplicado"})
    assert response.status_code == 200, response.text
    assert client.get("/api/multas").json()["total"] == 0
    detail = client.get(f"/api/multas/{fine['id']}").json()
    assert detail["eliminada_en"]
    assert detail["creado_por"] == "operador_demo"
    assert detail["actualizado_por"] == "operador_baja"
    assert any(entry["accion"] == "BAJA" and entry["usuario"] == "operador_baja" for entry in detail["historial"])
    assert client.post("/api/multas", json=multa_data).status_code == 409
    assert client.post("/api/pagos", json=pago_data).status_code == 422
    assert client.patch(f"/api/multas/{fine['id']}", json={"descripcion": "Cambio posterior"}).status_code == 409


def test_edits_preserve_temporal_relationship_and_payment_identity(client, multa_data, pago_data):
    fine = client.post("/api/multas", json=multa_data).json()
    payment = client.post("/api/pagos", json=pago_data).json()
    fine_url = f"/api/multas/{fine['id']}"
    payment_url = f"/api/pagos/{payment['id']}"

    after_payment = client.patch(fine_url, json={"fecha_infraccion": "2025-01-04", "fecha_registro": "2025-01-05"})
    assert after_payment.status_code == 409, after_payment.text
    assert client.get(fine_url).json()["fecha_infraccion"] == multa_data["fecha_infraccion"]
    assert client.patch(payment_url, json={"fecha_pago": "2024-12-31"}).status_code == 422
    assert client.patch(payment_url, json={"monto_pagado": "50.00"}).status_code == 422
    assert client.patch(payment_url, json={"dni_infractor": "11111111"}).status_code == 422
    assert client.patch(fine_url, json={"dni_infractor": "11111111"}).status_code == 409

    client.post("/api/auth/login", json={"username": "operador_correccion", "password": "demo"})
    correction = client.patch(payment_url, json={"fecha_pago": "2025-01-04", "metodo_pago": "TARJETA", "numero_comprobante": "TEST-CORREGIDO"})
    assert correction.status_code == 200, correction.text
    detail = client.get(payment_url).json()
    assert detail["numero_comprobante"] == "TEST-CORREGIDO"
    assert detail["actualizado_por"] == "operador_correccion"
    assert detail["creado_por"] == "operador_demo"
    assert detail["monto_pagado"] == "40.00"
    assert any(entry["accion"] == "EDICION" and entry["usuario"] == "operador_correccion" for entry in detail["historial"])


def test_composite_foreign_key_blocks_wrong_dni_even_outside_api(client, multa_data):
    from sqlalchemy.exc import IntegrityError
    from app.db.session import engine
    from app.modules.pagos.models import Pago

    assert client.post("/api/multas", json=multa_data).status_code == 201
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(Pago.__table__.insert().values(
                id=uuid4(), codigo_multa=multa_data["codigo_multa"], dni_infractor="99999999",
                fecha_pago=date(2025, 1, 3), monto_pagado=Decimal("10.00"), metodo_pago="EFECTIVO",
                numero_comprobante="DIRECTO-DB-001", creado_por="prueba_db", actualizado_por="prueba_db",
            ))
    assert client.get("/api/pagos").json()["total"] == 0


def test_concurrent_amount_reduction_and_payment_preserve_nonnegative_balance(client, application, multa_data, pago_data):
    from fastapi.testclient import TestClient

    fine = client.post("/api/multas", json=multa_data).json()

    def reduce_amount():
        with TestClient(application, raise_server_exceptions=False) as actor:
            actor.post("/api/auth/login", json={"username": "edicion", "password": "demo"})
            return actor.patch(f"/api/multas/{fine['id']}", json={"monto": "50.00"}).status_code

    def pay():
        with TestClient(application, raise_server_exceptions=False) as actor:
            actor.post("/api/auth/login", json={"username": "cobranza", "password": "demo"})
            return actor.post("/api/pagos", json={**pago_data, "monto_pagado": "80.00"}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        reducing = pool.submit(reduce_amount)
        paying = pool.submit(pay)
        statuses = (reducing.result(), paying.result())
    assert statuses in {(200, 409), (409, 201)}, statuses
    detail = client.get(f"/api/multas/{fine['id']}").json()
    assert Decimal(detail["saldo"]) >= 0
