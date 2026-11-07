from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auditoria.service import history
from app.modules.auth.dependencies import get_current_user
from app.modules.multas.models import Multa
from app.modules.multas.schemas import Motivo, MultaCreate, MultaUpdate
from app.modules.multas.service import create_multa, delete_multa, get_multa, serialize_multa, update_multa
from app.modules.pagos.models import Pago
from app.modules.pagos.service import serialize_pago
from app.shared.validators import fail

router = APIRouter(prefix="/multas", tags=["Multas"])


def paid_subquery():
    return select(Pago.codigo_multa.label("codigo"), func.sum(Pago.monto_pagado).label("pagado")).where(Pago.anulado_en.is_(None)).group_by(Pago.codigo_multa).subquery()


@router.get("")
def list_multas(q: str = "", estado: str = "", tipo_infraccion: str = "", desde: date | None = None, hasta: date | None = None, incluir_eliminadas: bool = False, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    paid = paid_subquery()
    paid_amount = func.coalesce(paid.c.pagado, 0)
    state = case((paid_amount == 0, "PENDIENTE"), (paid_amount >= Multa.monto, "PAGADA"), else_="PARCIAL")
    statement = select(Multa, paid_amount).outerjoin(paid, paid.c.codigo == Multa.codigo_multa)
    if not incluir_eliminadas:
        statement = statement.where(Multa.eliminada_en.is_(None))
    if q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Multa.codigo_multa.ilike(pattern), Multa.dni_infractor.ilike(pattern), Multa.lugar_infraccion.ilike(pattern)))
    if estado:
        if estado not in ("PENDIENTE", "PARCIAL", "PAGADA"):
            fail("Estado de cobranza inválido.")
        statement = statement.where(state == estado)
    if tipo_infraccion:
        statement = statement.where(Multa.tipo_infraccion == tipo_infraccion)
    if desde and hasta and desde > hasta:
        fail("La fecha inicial no puede ser posterior a la final.")
    if desde:
        statement = statement.where(Multa.fecha_infraccion >= desde)
    if hasta:
        statement = statement.where(Multa.fecha_infraccion <= hasta)
    count = db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = db.execute(statement.order_by(Multa.created_at.desc(), Multa.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [serialize_multa(db, multa, paid=amount) for multa, amount in rows], "total": count, "page": page, "page_size": page_size}


@router.post("", status_code=201)
def create(data: MultaCreate, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    multa = create_multa(db, data.model_dump(), username)
    db.commit()
    return serialize_multa(db, multa)


@router.get("/{multa_id}")
def detail(multa_id: UUID, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    multa = get_multa(db, multa_id)
    result = serialize_multa(db, multa)
    pagos = db.scalars(select(Pago).where(Pago.codigo_multa == multa.codigo_multa).order_by(Pago.fecha_pago.desc(), Pago.created_at.desc())).all()
    result["pagos"] = [serialize_pago(pago) for pago in pagos]
    result["historial"] = history(db, "multas", multa.id)
    return result


@router.patch("/{multa_id}")
def update(multa_id: UUID, data: MultaUpdate, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    multa = update_multa(db, multa_id, data.model_dump(exclude_unset=True), username)
    db.commit()
    return serialize_multa(db, multa)


@router.delete("/{multa_id}")
def delete(multa_id: UUID, data: Motivo, db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    multa = delete_multa(db, multa_id, data.motivo, username)
    db.commit()
    return serialize_multa(db, multa)
