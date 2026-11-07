import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Pago(Base):
    __tablename__ = "pagos"
    __table_args__ = (
        ForeignKeyConstraint(["codigo_multa", "dni_infractor"], ["multas.codigo_multa", "multas.dni_infractor"], ondelete="RESTRICT", onupdate="RESTRICT", name="fk_pago_multa_dni"),
        CheckConstraint("monto_pagado > 0 AND monto_pagado <= 9999999999.99", name="ck_pago_monto"),
        CheckConstraint("length(trim(numero_comprobante)) > 0", name="ck_pago_comprobante"),
        Index("ix_pagos_multa_dni", "codigo_multa", "dni_infractor"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    codigo_multa: Mapped[str] = mapped_column(String(18))
    dni_infractor: Mapped[str] = mapped_column(String(8), index=True)
    fecha_pago: Mapped[date] = mapped_column(Date, index=True)
    monto_pagado: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    metodo_pago: Mapped[str] = mapped_column(ForeignKey("metodos_pago.codigo", ondelete="RESTRICT"))
    numero_comprobante: Mapped[str] = mapped_column(String(120), unique=True)
    creado_por: Mapped[str] = mapped_column(String(80))
    actualizado_por: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_anulacion: Mapped[str | None] = mapped_column(Text)
