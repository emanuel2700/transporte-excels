from datetime import datetime, timezone

from sqlalchemy import select

from app.modules.auditoria.service import audit
from app.modules.catalogos.models import MetodoPago
from app.modules.multas.service import get_multa_by_code, total_pagado
from app.modules.pagos.models import Pago
from app.shared.validators import amount, code, dni, fail, money, parse_date, text, today

PAGO_FIELDS = ("codigo_multa", "dni_infractor", "fecha_pago", "monto_pagado", "metodo_pago", "numero_comprobante")


def validate_pago(db, data, existing=None, check_balance=True):
    normalized = {
        "codigo_multa": code(data.get("codigo_multa")),
        "dni_infractor": dni(data.get("dni_infractor")),
        "fecha_pago": parse_date(data.get("fecha_pago"), "fecha_pago"),
        "monto_pagado": amount(data.get("monto_pagado"), "monto_pagado"),
        "metodo_pago": text(data.get("metodo_pago"), "metodo_pago", 60),
        "numero_comprobante": text(data.get("numero_comprobante"), "numero_comprobante", 120),
    }
    multa = get_multa_by_code(db, normalized["codigo_multa"])
    if not multa or multa.eliminada_en:
        fail("codigo_multa: no existe una multa activa con ese código; regístrala primero.")
    if multa.dni_infractor != normalized["dni_infractor"]:
        fail("dni_infractor: no coincide con el DNI de la multa.")
    if normalized["fecha_pago"] > today():
        fail("fecha_pago: no puede ser futura.")
    if normalized["fecha_pago"] < multa.fecha_infraccion:
        fail("fecha_pago: no puede ser anterior a la infracción.")
    if not db.scalar(select(MetodoPago.id).where(MetodoPago.codigo == normalized["metodo_pago"])):
        fail("metodo_pago: el valor no pertenece al catálogo válido.")
    duplicate = db.scalar(select(Pago).where(Pago.numero_comprobante == normalized["numero_comprobante"]))
    if duplicate and (existing is None or duplicate.id != existing.id):
        fail("Ya existe un pago con ese número de comprobante, incluso si fue anulado.", 409)
    if check_balance:
        paid = total_pagado(db, multa.codigo_multa)
        if existing and not existing.anulado_en and existing.codigo_multa == multa.codigo_multa:
            paid -= existing.monto_pagado
        if normalized["monto_pagado"] > multa.monto - paid:
            fail(f"monto_pagado: supera el saldo disponible de {money(multa.monto - paid)}.", 409)
    warnings = []
    if normalized["fecha_pago"] < multa.fecha_registro:
        warnings.append("El pago es anterior al registro administrativo de la multa.")
    similar = select(Pago.id).where(Pago.codigo_multa == multa.codigo_multa, Pago.fecha_pago == normalized["fecha_pago"], Pago.monto_pagado == normalized["monto_pagado"], Pago.numero_comprobante != normalized["numero_comprobante"], Pago.anulado_en.is_(None))
    if existing:
        similar = similar.where(Pago.id != existing.id)
    if db.scalar(similar.limit(1)):
        warnings.append("Existe otro pago con la misma multa, fecha e importe y diferente comprobante; revisa un posible duplicado.")
    return normalized, warnings


def serialize_pago(pago):
    data = {key: getattr(pago, key) for key in PAGO_FIELDS}
    data.update({"id": str(pago.id), "monto_pagado": money(pago.monto_pagado), "creado_por": pago.creado_por, "actualizado_por": pago.actualizado_por, "created_at": pago.created_at, "updated_at": pago.updated_at, "anulado_en": pago.anulado_en, "motivo_anulacion": pago.motivo_anulacion})
    return data


def create_pago(db, data, username):
    codigo = code(data.get("codigo_multa"))
    get_multa_by_code(db, codigo, lock=True)
    normalized, _ = validate_pago(db, data)
    pago = Pago(**normalized, creado_por=username, actualizado_por=username)
    db.add(pago)
    db.flush()
    audit(db, "pagos", pago.id, "CREACION", username, {"despues": serialize_pago(pago)})
    db.flush()
    return pago


def get_pago(db, pago_id, lock=False):
    statement = select(Pago).where(Pago.id == pago_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    pago = db.scalar(statement)
    if not pago:
        fail("No se encontró el pago.", 404)
    return pago


def update_pago(db, pago_id, changes, username):
    # Keep the lock order consistent with create, cancellation and imports: multa then pago.
    initial = get_pago(db, pago_id)
    get_multa_by_code(db, initial.codigo_multa, lock=True)
    pago = get_pago(db, pago_id, lock=True)
    if pago.anulado_en:
        fail("No se puede editar un pago anulado.", 409)
    if set(changes) - {"fecha_pago", "metodo_pago", "numero_comprobante"}:
        fail("Solo se pueden corregir fecha, método y comprobante; para cambiar importe o multa anula el pago y crea uno nuevo.")
    before = serialize_pago(pago)
    data = {key: getattr(pago, key) for key in PAGO_FIELDS}
    data.update(changes)
    normalized, _ = validate_pago(db, data, existing=pago)
    for key in changes:
        setattr(pago, key, normalized[key])
    pago.actualizado_por = username
    pago.updated_at = datetime.now(timezone.utc)
    db.flush()
    audit(db, "pagos", pago.id, "EDICION", username, {"antes": before, "despues": serialize_pago(pago)})
    db.flush()
    return pago


def delete_pago(db, pago_id, motivo, username):
    initial = get_pago(db, pago_id)
    get_multa_by_code(db, initial.codigo_multa, lock=True)
    pago = get_pago(db, pago_id, lock=True)
    motivo = text(motivo, "motivo", 1000)
    if pago.anulado_en:
        fail("El pago ya fue anulado.", 409)
    pago.anulado_en = datetime.now(timezone.utc)
    pago.motivo_anulacion = motivo
    pago.actualizado_por = username
    pago.updated_at = datetime.now(timezone.utc)
    audit(db, "pagos", pago.id, "ANULACION", username, {"motivo": motivo})
    db.flush()
    return pago
