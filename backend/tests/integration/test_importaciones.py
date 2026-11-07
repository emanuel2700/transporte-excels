import csv
import io


def upload(client, area, rows, **config):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    response = client.post("/api/importaciones", files={"file": ("prueba.csv", output.getvalue().encode(), "text/csv")}, data={
        "area": area, "encoding": "utf-8-sig", "delimiter": ",", "date_format": "iso", "decimal_separator": ".", **config,
    })
    assert response.status_code in (200, 201), response.text
    return response.json()


def confirm(client, batch):
    return client.post(f"/api/importaciones/{batch['id']}/confirmar", json={"aceptar_advertencias": True})


def test_preview_edit_validate_confirm_and_idempotent_retry(client, multa_data):
    row = {**multa_data, "estado_multa": "PENDIENTE"}
    batch = upload(client, "multas", [row, {**row, "codigo_multa": "MUL-00000000000002", "dni_infractor": "123"}])
    assert batch["resumen"]["listas"] == 1
    assert batch["resumen"]["errores"] == 1
    assert client.get("/api/multas").json()["total"] == 0
    invalid = next(item for item in batch["filas"] if item["errores"])
    updated = client.patch(f"/api/importaciones/{batch['id']}/filas/{invalid['id']}", json={"datos": {**invalid["datos"], "dni_infractor": "12345678"}})
    assert updated.status_code == 200, updated.text
    validated = client.post(f"/api/importaciones/{batch['id']}/validar")
    assert validated.status_code == 200, validated.text
    assert validated.json()["resumen"]["errores"] == 0
    result = confirm(client, batch)
    assert result.status_code == 200, result.text
    assert result.json()["estado"] == "CONFIRMADA"
    assert result.json()["resumen"]["importadas"] == 2
    assert confirm(client, batch).status_code == 200
    assert client.get("/api/multas").json()["total"] == 2


def test_cancel_purges_staged_personal_data_and_writes_nothing(client, multa_data):
    batch = upload(client, "multas", [{**multa_data, "estado_multa": "PENDIENTE"}])
    response = client.post(f"/api/importaciones/{batch['id']}/cancelar")
    assert response.status_code == 200, response.text
    assert response.json()["estado"] == "CANCELADA"
    assert response.json()["filas"] == []
    assert confirm(client, batch).status_code == 409
    assert client.get("/api/multas").json()["total"] == 0


def test_duplicate_exact_skipped_but_conflicting_duplicates_blocked(client, multa_data):
    row = {**multa_data, "estado_multa": "PENDIENTE"}
    batch = upload(client, "multas", [row, row])
    assert batch["resumen"]["excluidas"] == 1
    assert confirm(client, batch).status_code == 200
    assert client.get("/api/multas").json()["total"] == 1
    existing = upload(client, "multas", [row])
    assert existing["resumen"]["excluidas"] == 1
    conflicting = upload(client, "multas", [{**row, "monto": "101.00"}])
    assert conflicting["resumen"]["errores"] == 1


def test_payment_import_validates_aggregate_balance_and_missing_fine(client, multa_data, pago_data):
    missing = upload(client, "pagos", [pago_data])
    assert missing["resumen"]["errores"] == 1
    client.post("/api/multas", json=multa_data)
    batch = upload(client, "pagos", [
        {**pago_data, "monto_pagado": "60.00"},
        {**pago_data, "monto_pagado": "60.00", "numero_comprobante": "TEST-002"},
    ])
    assert batch["resumen"]["errores"] > 0
    assert client.get("/api/pagos").json()["total"] == 0


def test_concurrent_database_change_does_not_silently_change_selection(client, multa_data):
    row = {**multa_data, "estado_multa": "PENDIENTE"}
    batch = upload(client, "multas", [row, {**row, "codigo_multa": "MUL-00000000000002"}])
    client.post("/api/multas", json={**multa_data, "monto": "111.00"})
    result = confirm(client, batch)
    assert result.status_code == 409, result.text
    assert client.get("/api/multas").json()["total"] == 1
    assert client.get(f"/api/importaciones/{batch['id']}").json()["estado"] == "BORRADOR"


def test_save_failure_rolls_back_entire_batch(client, multa_data, monkeypatch):
    import app.modules.importaciones.service as service
    original = service.create_multa
    counter = 0

    def fail_second(*args, **kwargs):
        nonlocal counter
        counter += 1
        if counter == 2:
            raise RuntimeError("Fallo de guardado simulado")
        return original(*args, **kwargs)

    row = {**multa_data, "estado_multa": "PENDIENTE"}
    batch = upload(client, "multas", [row, {**row, "codigo_multa": "MUL-00000000000002"}])
    monkeypatch.setattr(service, "create_multa", fail_second)
    result = confirm(client, batch)
    assert result.status_code >= 400, result.text
    assert client.get("/api/multas").json()["total"] == 0
    assert client.get(f"/api/importaciones/{batch['id']}").json()["estado"] == "BORRADOR"


def test_stated_paid_status_never_creates_fictitious_payment(client, multa_data):
    batch = upload(client, "multas", [{**multa_data, "estado_multa": "PAGADA"}])
    assert batch["resumen"]["advertencias"] == 1
    assert confirm(client, batch).status_code == 200
    assert client.get("/api/multas").json()["items"][0]["estado_multa"] == "PENDIENTE"
    assert client.get("/api/pagos").json()["total"] == 0


def test_confirmation_imports_only_reviewed_eligible_rows(client, multa_data):
    row = {**multa_data, "estado_multa": "PENDIENTE"}
    batch = upload(client, "multas", [
        row,
        {**row, "codigo_multa": "MUL-00000000000002", "dni_infractor": "inválido"},
        {**row, "codigo_multa": "MUL-00000000000003"},
    ])
    excluded = batch["filas"][2]
    updated = client.patch(f"/api/importaciones/{batch['id']}/filas/{excluded['id']}", json={"excluida": True})
    assert updated.status_code == 200, updated.text
    assert updated.json()["resumen"] == {
        "listas": 1, "advertencias": 0, "errores": 1, "excluidas": 1, "vacias": 0, "importadas": 0,
    }
    saved = confirm(client, batch)
    assert saved.status_code == 200, saved.text
    assert saved.json()["resumen"]["importadas"] == 1
    assert saved.json()["resumen"]["errores"] == 1
    assert saved.json()["resumen"]["excluidas"] == 1
    assert client.get("/api/multas").json()["total"] == 1


def test_expired_draft_purges_data_and_cannot_be_confirmed(client, multa_data):
    from datetime import datetime, timedelta, timezone
    from uuid import UUID
    from app.db.session import SessionLocal
    from app.modules.importaciones.models import Importacion

    batch = upload(client, "multas", [{**multa_data, "estado_multa": "PENDIENTE"}])
    with SessionLocal() as db:
        record = db.get(Importacion, UUID(batch["id"]))
        record.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    expired = client.get(f"/api/importaciones/{batch['id']}")
    assert expired.status_code == 200, expired.text
    assert expired.json()["estado"] == "EXPIRADA"
    assert expired.json()["filas"] == []
    assert expired.json()["resumen"]["listas"] == 1
    assert confirm(client, batch).status_code == 409
    assert client.get("/api/multas").json()["total"] == 0
