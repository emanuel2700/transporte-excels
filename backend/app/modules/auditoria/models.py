import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (Index("ix_auditoria_entidad", "entidad", "registro_id"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entidad: Mapped[str] = mapped_column(String(30))
    registro_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    accion: Mapped[str] = mapped_column(String(30))
    usuario: Mapped[str] = mapped_column(String(80))
    detalle: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
