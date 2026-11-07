from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from app.modules.auditoria.models import Auditoria


def audit(db, entidad, registro_id, accion, usuario, detalle):
    db.add(Auditoria(entidad=entidad, registro_id=registro_id, accion=accion, usuario=usuario, detalle=jsonable_encoder(detalle)))


def history(db, entidad, registro_id):
    entries = db.scalars(select(Auditoria).where(Auditoria.entidad == entidad, Auditoria.registro_id == registro_id).order_by(Auditoria.created_at.desc())).all()
    return [{"id": str(x.id), "accion": x.accion, "usuario": x.usuario, "created_at": x.created_at, "detalle": x.detalle} for x in entries]
