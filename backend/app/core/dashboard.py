from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.multas.models import Multa
from app.modules.multas.router import paid_subquery
from app.modules.pagos.models import Pago
from app.shared.validators import money, today

router = APIRouter(tags=["Resumen"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    paid = paid_subquery()
    balance = Multa.monto - func.coalesce(paid.c.pagado, 0)
    result = db.execute(select(func.count(Multa.id), func.coalesce(func.sum(Multa.monto), 0), func.coalesce(func.sum(paid.c.pagado), 0), func.coalesce(func.sum(balance), 0), func.coalesce(func.sum(case(((balance > 0) & (Multa.fecha_vencimiento < today()), 1), else_=0)), 0)).outerjoin(paid, paid.c.codigo == Multa.codigo_multa).where(Multa.eliminada_en.is_(None))).one()
    payment_count = db.scalar(select(func.count(Pago.id)).where(Pago.anulado_en.is_(None)))
    return {"multas": result[0], "total_multas": money(result[1]), "total_pagado": money(result[2]), "saldo_pendiente": money(result[3]), "multas_vencidas": result[4], "pagos": payment_count}
