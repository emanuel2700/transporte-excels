from typing import Any

from pydantic import BaseModel, ConfigDict


class MultaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo_multa: str
    dni_infractor: str
    tipo_infraccion: str
    descripcion: str = ""
    fecha_infraccion: str
    lugar_infraccion: str
    monto: Any
    fecha_vencimiento: str
    fecha_registro: str


class MultaUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    codigo_multa: str | None = None
    dni_infractor: str | None = None
    tipo_infraccion: str | None = None
    descripcion: str | None = None
    fecha_infraccion: str | None = None
    lugar_infraccion: str | None = None
    monto: Any = None
    fecha_vencimiento: str | None = None
    fecha_registro: str | None = None


class Motivo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: str
