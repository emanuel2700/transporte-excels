from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.modules.auditoria.service import audit
from app.modules.catalogos.models import TipoInfraccion
from app.modules.multas.models import Multa
from app.modules.pagos.models import Pago
from app.shared.validators import amount, code, dni, fail, money, parse_date, text, today

MULTA_FIELDS = ("codigo_multa", "dni_infractor", "tipo_infraccion", "descripcion", "fecha_infraccion", "lugar_infraccion", "monto", "fecha_vencimiento", "fecha_registro")


def get_multa_by_code(db, codigo, lock=False):
    statement = select(Multa).where(Multa.codigo_multa == codigo)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return db.scalar(statement)


def total_pagado(db, codigo):
    return db.scalar(select(func.coalesce(func.sum(Pago.monto_pagado), 0)).where(Pago.codigo_multa == codigo, Pago.anulado_en.is_(None))) or Decimal("0")


def validate_multa(db, data, existing=None):
    normalized = {
        "codigo_multa": code(data.get("codigo_multa")),
        "dni_infractor": dni(data.get("dni_infractor")),
        "tipo_infraccion": text(data.get("tipo_infraccion"), "tipo_infraccion", 60),
        "descripcion": text(data.get("descripcion"), "descripcion", 5000, required=False),
        "lugar_infraccion": text(data.get("lugar_infraccion"), "lugar_infraccion", 255),
        "monto": amount(data.get("monto"), "monto"),
        "fecha_infraccion": parse_date(data.get("fecha_infraccion"), "fecha_infraccion"),
        "fecha_registro": parse_date(data.get("fecha_registro"), "fecha_registro"),
        "fecha_vencimiento": parse_date(data.get("fecha_vencimiento"), "fecha_vencimiento"),
    }
    if normalized["fecha_infraccion"] > normalized["fecha_registro"]:
        fail("fecha_registro: no puede ser anterior a la fecha de infracción.")
    if normalized["fecha_registro"] > today():
        fail("fecha_registro: no puede ser futura.")
    if normalized["fecha_vencimiento"] < normalized["fecha_registro"]:
        fail("fecha_vencimiento: no puede ser anterior a la fecha de registro.")
    if not db.scalar(select(TipoInfraccion.id).where(TipoInfraccion.codigo == normalized["tipo_infraccion"])):
        fail("tipo_infraccion: el valor no pertenece al catálogo válido.")
    duplicate = get_multa_by_code(db, normalized["codigo_multa"])
    if duplicate and (existing is None or duplicate.id != existing.id):
        fail("Ya existe una multa con ese código, incluso si fue dada de baja.", 409)
    warnings = []
    if not normalized["descripcion"]:
        warnings.append("La multa no tiene descripción.")
    return normalized, warnings


def serialize_multa(db, multa, paid=None):
    paid = total_pagado(db, multa.codigo_multa) if paid is None else Decimal(paid)
    saldo = multa.monto - paid
    state = "PENDIENTE" if paid == 0 else "PAGADA" if saldo <= 0 else "PARCIAL"
    data = {key: getattr(multa, key) for key in MULTA_FIELDS}
    data.update({
        "id": str(multa.id), "monto": money(multa.monto), "estado_multa": state,
        "total_pagado": money(paid), "saldo": money(saldo),
        "vencida": saldo > 0 and multa.fecha_vencimiento < today(),
        "creado_por": multa.creado_por, "actualizado_por": multa.actualizado_por,
        "created_at": multa.created_at, "updated_at": multa.updated_at,
        "eliminada_en": multa.eliminada_en, "motivo_eliminacion": multa.motivo_eliminacion,
    })
    return data


def create_multa(db, data, username):
    normalized, _ = validate_multa(db, data)
    multa = Multa(**normalized, creado_por=username, actualizado_por=username)
    db.add(multa)
    db.flush()
    audit(db, "multas", multa.id, "CREACION", username, {"despues": serialize_multa(db, multa)})
    db.flush()
    return multa


def get_multa(db, multa_id, lock=False):
    statement = select(Multa).where(Multa.id == multa_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    multa = db.scalar(statement)
    if not multa:
        fail("No se encontró la multa.", 404)
    return multa


def update_multa(db, multa_id, changes, username):
    multa = get_multa(db, multa_id, lock=True)
    if multa.eliminada_en:
        fail("No se puede editar una multa dada de baja.", 409)
    before = serialize_multa(db, multa)
    data = {key: getattr(multa, key) for key in MULTA_FIELDS}
    data.update(changes)
    normalized, _ = validate_multa(db, data, existing=multa)
    if normalized["codigo_multa"] != multa.codigo_multa:
        fail("El código de la multa no se puede modificar.")
    if normalized["dni_infractor"] != multa.dni_infractor and db.scalar(select(Pago.id).where(Pago.codigo_multa == multa.codigo_multa).limit(1)):
        fail("No se puede cambiar el DNI de una multa con pagos asociados.", 409)
    if normalized["monto"] < total_pagado(db, multa.codigo_multa):
        fail("El monto no puede ser menor que el total pagado vigente.", 409)
    earliest_payment = db.scalar(select(func.min(Pago.fecha_pago)).where(Pago.codigo_multa == multa.codigo_multa, Pago.anulado_en.is_(None)))
    if earliest_payment and normalized["fecha_infraccion"] > earliest_payment:
        fail("La infracción no puede quedar después de un pago vigente.", 409)
    for key, value in normalized.items():
        setattr(multa, key, value)
    multa.actualizado_por = username
    multa.updated_at = datetime.now(timezone.utc)
    db.flush()
    audit(db, "multas", multa.id, "EDICION", username, {"antes": before, "despues": serialize_multa(db, multa)})
    db.flush()
    return multa


def delete_multa(db, multa_id, motivo, username):
    multa = get_multa(db, multa_id, lock=True)
    motivo = text(motivo, "motivo", 1000)
    if multa.eliminada_en:
        fail("La multa ya está dada de baja.", 409)
    if db.scalar(select(Pago.id).where(Pago.codigo_multa == multa.codigo_multa).limit(1)):
        fail("No se puede dar de baja una multa con pagos asociados, incluidos los anulados.", 409)
    multa.eliminada_en = datetime.now(timezone.utc)
    multa.motivo_eliminacion = motivo
    multa.actualizado_por = username
    multa.updated_at = datetime.now(timezone.utc)
    audit(db, "multas", multa.id, "BAJA", username, {"motivo": motivo})
    db.flush()
    return multa
