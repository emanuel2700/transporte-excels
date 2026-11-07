"""Borradores aislados de las tablas definitivas de multas y pagos."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Importacion(Base):
    __tablename__ = "importaciones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    area: Mapped[str] = mapped_column(String(16), nullable=False)
    nombre_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), nullable=False, default="BORRADOR", index=True)
    creado_por: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: utcnow() + timedelta(hours=24), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    configuracion: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mensajes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    vacias: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_original: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resumen_final: Mapped[dict | None] = mapped_column(JSON)


class FilaImportacion(Base):
    __tablename__ = "filas_importacion"
    __table_args__ = (
        UniqueConstraint("importacion_id", "numero_fila", name="uq_importacion_numero_fila"),
        Index("ix_importacion_resultado", "importacion_id", "resultado"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    importacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("importaciones.id", ondelete="CASCADE"), nullable=False
    )
    numero_fila: Mapped[int] = mapped_column(Integer, nullable=False)
    datos_originales: Mapped[dict] = mapped_column(JSON, nullable=False)
    datos: Mapped[dict] = mapped_column(JSON, nullable=False)
    errores: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    advertencias: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    excluida: Mapped[bool] = mapped_column(nullable=False, default=False)
    resultado: Mapped[str] = mapped_column(String(16), nullable=False, default="VALIDA")
    error_estructura: Mapped[str | None] = mapped_column(Text)
    registro_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
