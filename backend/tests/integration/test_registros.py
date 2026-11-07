from concurrent.futures import ThreadPoolExecutor

import pytest


def test_demo_session_and_actor_are_server_controlled(client, multa_data):
    assert client.get("/api/auth/me").json()["username"] == "operador_demo"
    created = client.post("/api/multas", json=multa_data)
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["creado_por"] == "operador_demo"
    assert data["dni_infractor"] == "01234567"
    assert data["estado_multa"] == "PENDIENTE"
    client.post("/api/auth/logout")
    assert client.get("/api/multas").status_code == 401


@pytest.mark.parametrize("field,value", [
    ("dni_infractor", "1234567"), ("dni_infractor", "１２３４５６７８"),
    ("codigo_multa", "MUL-123"), ("monto", "NaN"),
    ("monto", "Infinity"), ("monto", "0"), ("monto", "-1"),
    ("monto", "1.234"), ("fecha_infraccion", "2025-02-30"),
    ("fecha_vencimiento", "2025-01-01"), ("tipo_infraccion", "INVENTADO"),
])
def test_invalid_fine_is_rejected(client, multa_data, field, value):
    response = client.post("/api/multas", json={**multa_data, field: value})
    assert response.status_code == 422, response.text
    assert client.get("/api/multas").json()["total"] == 0


def test_payments_require_existing_fine_matching_dni_and_balance(client, multa_data, pago_data):
    assert client.post("/api/pagos", json=pago_data).status_code in (409, 422)
    fine = client.post("/api/multas", json=multa_data).json()
    assert client.post("/api/pagos", json={**pago_data, "dni_infractor": "11111111"}).status_code in (409, 422)
    payment = client.post("/api/pagos", json=pago_data)
    assert payment.status_code == 201, payment.text
    detail = client.get(f"/api/multas/{fine['id']}").json()
    assert detail["estado_multa"] == "PARCIAL"
    assert detail["saldo"] == "60.00"
    assert client.post("/api/pagos", json={**pago_data, "numero_comprobante": "TEST-002", "monto_pagado": "61.00"}).status_code in (409, 422)
    assert client.patch(f"/api/multas/{fine['id']}", json={"monto": "39.00"}).status_code in (409, 422)
    assert client.request("DELETE", f"/api/multas/{fine['id']}", json={"motivo": "No se permite"}).status_code in (409, 422)
    paid = client.post("/api/pagos", json={**pago_data, "numero_comprobante": "TEST-003", "monto_pagado": "60.00"})
    assert paid.status_code == 201, paid.text
    assert client.get(f"/api/multas/{fine['id']}").json()["estado_multa"] == "PAGADA"


def test_payment_void_keeps_history_and_receipt_reserved(client, multa_data, pago_data):
    fine = client.post("/api/multas", json=multa_data).json()
    payment = client.post("/api/pagos", json=pago_data).json()
    client.post("/api/auth/login", json={"username": "segundo_operador", "password": "otra"})
    result = client.request("DELETE", f"/api/pagos/{payment['id']}", json={"motivo": "Corrección de prueba"})
    assert result.status_code in (200, 204), result.text
    detail = client.get(f"/api/pagos/{payment['id']}").json()
    assert detail["anulado_en"]
    assert detail["actualizado_por"] == "segundo_operador"
    assert detail["historial"]
    assert client.get(f"/api/multas/{fine['id']}").json()["saldo"] == "100.00"
    assert client.post("/api/pagos", json=pago_data).status_code in (409, 422)


def test_two_concurrent_payments_cannot_exceed_balance(client, application, multa_data, pago_data):
    from fastapi.testclient import TestClient
    fine = client.post("/api/multas", json=multa_data).json()

    def pay(receipt):
        with TestClient(application, raise_server_exceptions=False) as other:
            other.post("/api/auth/login", json={"username": receipt, "password": "demo"})
            return other.post("/api/pagos", json={**pago_data, "monto_pagado": "80.00", "numero_comprobante": receipt}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(pay, ["CONC-1", "CONC-2"]))
    assert statuses.count(201) == 1, statuses
    assert any(status in (409, 422) for status in statuses), statuses
    assert client.get(f"/api/multas/{fine['id']}").json()["saldo"] == "20.00"
