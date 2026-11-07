from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.catalogos.models import MetodoPago, TipoInfraccion

router = APIRouter(tags=["Catálogos"])


@router.get("/catalogos")
def catalogs(db: Session = Depends(get_db), username: str = Depends(get_current_user)):
    return {
        "tipos_infraccion": [{"codigo": x.codigo, "nombre": x.nombre} for x in db.scalars(select(TipoInfraccion).order_by(TipoInfraccion.nombre))],
        "metodos_pago": [{"codigo": x.codigo, "nombre": x.nombre} for x in db.scalars(select(MetodoPago).order_by(MetodoPago.nombre))],
    }
