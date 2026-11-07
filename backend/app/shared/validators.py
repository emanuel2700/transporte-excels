import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from fastapi import HTTPException

CODE_RE = re.compile(r"^MUL-[0-9]{14}$")
DNI_RE = re.compile(r"^[0-9]{8}$")
MAX_AMOUNT = Decimal("9999999999.99")


def today() -> date:
    return datetime.now(ZoneInfo("America/Lima")).date()


def fail(message: str, status: int = 422):
    raise HTTPException(status_code=status, detail=message)


def text(value, field: str, maximum: int = 255, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        fail(f"{field}: debe ser texto.")
    value = value.strip()
    if required and not value:
        fail(f"{field}: es obligatorio.")
    if len(value) > maximum:
        fail(f"{field}: máximo {maximum} caracteres.")
    return value


def code(value) -> str:
    value = text(value, "codigo_multa", 18)
    if not CODE_RE.fullmatch(value):
        fail("codigo_multa: use MUL- seguido de exactamente 14 dígitos.")
    return value


def dni(value) -> str:
    value = text(value, "dni_infractor", 8)
    if not DNI_RE.fullmatch(value):
        fail("dni_infractor: debe contener exactamente ocho dígitos numéricos.")
    return value


def amount(value, field: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        fail(f"{field}: importe inválido.")
    raw = str(value).strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", raw):
        fail(f"{field}: use un número positivo con punto decimal y hasta dos decimales.")
    try:
        parsed = Decimal(raw)
    except InvalidOperation:
        fail(f"{field}: importe inválido.")
    if not parsed.is_finite() or parsed <= 0 or parsed > MAX_AMOUNT:
        fail(f"{field}: debe ser mayor que cero y no superar {MAX_AMOUNT}.")
    return parsed


def parse_date(value, field: str) -> date:
    if isinstance(value, datetime):
        fail(f"{field}: debe ser una fecha sin hora.")
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value.strip()):
        fail(f"{field}: use AAAA-MM-DD.")
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        fail(f"{field}: fecha inexistente o inválida.")


def money(value) -> str:
    return format(Decimal(value or 0), ".2f")
