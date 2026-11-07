import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Multa(Base):
    __tablename__ = "multas"
    __table_args__ = (
        UniqueConstraint("codigo_multa", "dni_infractor", name="uq_multa_codigo_dni"),
        CheckConstraint("codigo_multa ~ '^MUL-[0-9]{14}$'", name="ck_multa_codigo"),
        CheckConstraint("dni_infractor ~ '^[0-9]{8}$'", name="ck_multa_dni"),
        CheckConstraint("monto > 0 AND monto <= 9999999999.99", name="ck_multa_monto"),
        CheckConstraint("fecha_infraccion <= fecha_registro", name="ck_multa_fechas_registro"),
        CheckConstraint("fecha_vencimiento >= fecha_registro", name="ck_multa_fechas_vencimiento"),
        CheckConstraint("length(trim(lugar_infraccion)) > 0", name="ck_multa_lugar"),
        Index("ix_multas_vencimiento", "fecha_vencimiento"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    codigo_multa: Mapped[str] = mapped_column(String(18), unique=True)
    dni_infractor: Mapped[str] = mapped_column(String(8), index=True)
    tipo_infraccion: Mapped[str] = mapped_column(ForeignKey("tipos_infraccion.codigo", ondelete="RESTRICT"), index=True)
    descripcion: Mapped[str] = mapped_column(Text, default="")
    fecha_infraccion: Mapped[date] = mapped_column(Date, index=True)
    lugar_infraccion: Mapped[str] = mapped_column(String(255))
    monto: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    fecha_registro: Mapped[date] = mapped_column(Date)
    creado_por: Mapped[str] = mapped_column(String(80))
    actualizado_por: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    eliminada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_eliminacion: Mapped[str | None] = mapped_column(Text)
