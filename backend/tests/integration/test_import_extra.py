"""Carreras reales en PostgreSQL: idempotencia y comprobantes compartidos."""

import csv
import io
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient


def upload(client, area, rows):
    content = io.StringIO(newline="")
    writer = csv.DictWriter(content, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    response = client.post("/api/importaciones", data={"area": area},
                           files={"file": ("concurrencia.csv", content.getvalue().encode(), "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()


def confirm_separately(application, batch_id, barrier):
    with TestClient(application, raise_server_exceptions=False) as browser:
        login = browser.post("/api/auth/login", json={"username": "operador_demo", "password": "demo"})
        assert login.status_code == 200, login.text
        barrier.wait(timeout=15)
        return browser.post(f"/api/importaciones/{batch_id}/confirmar", json={"aceptar_advertencias": True})


def test_simultaneous_retries_of_same_batch_create_records_once(client, application, multa_data):
    batch = upload(client, "multas", [{**multa_data, "estado_multa": "PENDIENTE"}])
    gate = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(confirm_separately, application, batch["id"], gate) for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert [result.status_code for result in results] == [200, 200], [result.text for result in results]
    assert all(result.json()["resumen"]["importadas"] == 1 for result in results)
    assert client.get("/api/multas").json()["total"] == 1
    assert results[0].json()["filas"][0]["registro_id"] == results[1].json()["filas"][0]["registro_id"]


def test_competing_batches_cannot_duplicate_receipt(client, application, multa_data, pago_data, monkeypatch):
    import app.modules.importaciones.service as service

    second_code = "MUL-00000000000002"
    for code in [multa_data["codigo_multa"], second_code]:
        response = client.post("/api/multas", json={**multa_data, "codigo_multa": code})
        assert response.status_code == 201, response.text
    batches = [upload(client, "pagos", [{**pago_data, "codigo_multa": code}])
               for code in [multa_data["codigo_multa"], second_code]]

    # Ambas transacciones validan mientras el comprobante sigue libre. La
    # restricción UNIQUE decide el ganador y revierte la transacción perdedora.
    after_validation = Barrier(2)
    original_validate = service.validate_batch

    def validate_then_wait(*args, **kwargs):
        result = original_validate(*args, **kwargs)
        after_validation.wait(timeout=15)
        return result

    monkeypatch.setattr(service, "validate_batch", validate_then_wait)
    start = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(confirm_separately, application, batch["id"], start) for batch in batches]
        results = [future.result(timeout=30) for future in futures]
    statuses = sorted(response.status_code for response in results)
    assert statuses == [200, 409], [response.text for response in results]
    assert client.get("/api/pagos").json()["total"] == 1
    states = [client.get(f"/api/importaciones/{batch['id']}").json()["estado"] for batch in batches]
    assert sorted(states) == ["BORRADOR", "CONFIRMADA"]


def test_draft_has_no_owner_permissions_and_confirmation_attributes_actual_session(client, multa_data):
    client.post("/api/auth/login", json={"username": "Alice", "password": "demo"})
    batch = upload(client, "multas", [{**multa_data, "estado_multa": "PENDIENTE"}])
    assert batch["creado_por"] == "Alice"
    row = batch["filas"][0]

    client.post("/api/auth/login", json={"username": "Bob", "password": "otra"})
    edited = client.patch(f"/api/importaciones/{batch['id']}/filas/{row['id']}",
                          json={"datos": {"descripcion": "Corrección declarada por Bob"}})
    assert edited.status_code == 200, edited.text
    assert client.post(f"/api/importaciones/{batch['id']}/validar").status_code == 200
    confirmed = client.post(f"/api/importaciones/{batch['id']}/confirmar", json={"aceptar_advertencias": True})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["creado_por"] == "Alice"
    record_id = confirmed.json()["filas"][0]["registro_id"]
    record = client.get(f"/api/multas/{record_id}").json()
    assert record["creado_por"] == "Bob"
    assert record["descripcion"] == "Corrección declarada por Bob"
    assert record["historial"][0]["usuario"] == "Bob"

    # Reintentar desde otra sesión devuelve el mismo resultado sin cambiar el actor.
    client.post("/api/auth/login", json={"username": "Alice", "password": "demo"})
    retried = client.post(f"/api/importaciones/{batch['id']}/confirmar", json={"aceptar_advertencias": True})
    assert retried.status_code == 200, retried.text
    assert client.get(f"/api/multas/{record_id}").json()["creado_por"] == "Bob"


def test_another_demo_user_can_cancel_draft(client, multa_data):
    client.post("/api/auth/login", json={"username": "Alice", "password": "demo"})
    batch = upload(client, "multas", [{**multa_data, "estado_multa": "PENDIENTE"}])
    client.post("/api/auth/login", json={"username": "Bob", "password": "otra"})
    cancelled = client.post(f"/api/importaciones/{batch['id']}/cancelar")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["estado"] == "CANCELADA"
    assert cancelled.json()["creado_por"] == "Alice"
    assert cancelled.json()["filas"] == []
    assert client.get("/api/multas").json()["total"] == 0
