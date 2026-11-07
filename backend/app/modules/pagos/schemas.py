from typing import Any

from pydantic import BaseModel, ConfigDict


class PagoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo_multa: str
    dni_infractor: str
    fecha_pago: str
    monto_pagado: Any
    metodo_pago: str
    numero_comprobante: str


class PagoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fecha_pago: str | None = None
    metodo_pago: str | None = None
    numero_comprobante: str | None = None
