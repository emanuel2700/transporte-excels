from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auditoria.service import history
from app.modules.auth.dependencies import get_current_user
from app.modules.multas.schemas import Motivo
from app.modules.pagos.models import Pago
from app.modules.pagos.schemas import PagoCreate, PagoUpdate
from app.modules.pagos.service import create_pago, delete_pago, get_pago, serialize_pago, update_pago, validate_pago
from app.shared.validators import fail

router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.get("")
def list_pagos(q: str = "", metodo_pago: str = "", desde: date | None = None, hasta: date | None = None, incluir_anulados: bool = False, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    statement = select(Pago)
    if not incluir_anulados:
        statement = statement.where(Pago.anulado_en.is_(None))
    if q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Pago.codigo_multa.ilike(pattern), Pago.dni_infractor.ilike(pattern), Pago.numero_comprobante.ilike(pattern)))
    if metodo_pago:
        statement = statement.where(Pago.metodo_pago == metodo_pago)
    if desde and hasta and desde > hasta:
        fail("La fecha inicial no puede ser posterior a la final.")
    if desde:
        statement = statement.where(Pago.fecha_pago >= desde)
    if hasta:
        statement = statement.where(Pago.fecha_pago <= hasta)
    count = db.scalar(select(func.count()).select_from(statement.subquery()))
    pagos = db.scalars(statement.order_by(Pago.fecha_pago.desc(), Pago.created_at.desc(), Pago.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize_pago(pago) for pago in pagos], "total": count, "page": page, "page_size": page_size}


@router.post("", status_code=201)
def create(data: PagoCreate, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    pago = create_pago(db, data.model_dump(), username)
    _, warnings = validate_pago(db, data.model_dump(), existing=pago)
    db.commit()
    return {**serialize_pago(pago), "advertencias": warnings}


@router.get("/{pago_id}")
def detail(pago_id: UUID, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    pago = get_pago(db, pago_id)
    return {**serialize_pago(pago), "historial": history(db, "pagos", pago.id)}


@router.patch("/{pago_id}")
def update(pago_id: UUID, data: PagoUpdate, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    pago = update_pago(db, pago_id, data.model_dump(exclude_unset=True), username)
    db.commit()
    return serialize_pago(pago)


@router.delete("/{pago_id}")
def delete(pago_id: UUID, data: Motivo, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    pago = delete_pago(db, pago_id, data.motivo, username)
    db.commit()
    return serialize_pago(pago)
