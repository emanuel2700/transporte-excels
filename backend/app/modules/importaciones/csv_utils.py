"""Lectura estricta de CSV, sin inferir formatos de fechas o importes."""

import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 20_000
FIELDS = {
    "multas": [
        "codigo_multa", "dni_infractor", "tipo_infraccion", "descripcion",
        "fecha_infraccion", "lugar_infraccion", "monto", "estado_multa",
        "fecha_vencimiento", "fecha_registro",
    ],
    "pagos": [
        "codigo_multa", "fecha_pago", "monto_pagado", "metodo_pago",
        "numero_comprobante", "dni_infractor",
    ],
}


def read_csv(content: bytes, area: str, config: dict, mapping: dict) -> tuple[list, list, int]:
    if area not in FIELDS:
        raise HTTPException(422, "El área debe ser multas o pagos.")
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "El archivo supera el límite de 10 MB.")
    if not content:
        raise HTTPException(422, "El archivo está vacío.")
    if config["encoding"] not in {"utf-8-sig", "cp1252"}:
        raise HTTPException(422, "La codificación debe ser UTF-8 o Windows-1252.")
    if config["delimiter"] not in {",", ";", "\t"}:
        raise HTTPException(422, "Seleccione coma, punto y coma o tabulación como separador.")
    if config["date_format"] not in {"iso", "dmy"} or config["decimal_separator"] not in {".", ","}:
        raise HTTPException(422, "Formato de fecha o separador decimal no permitido.")
    try:
        source = content.decode(config["encoding"], errors="strict")
    except UnicodeDecodeError:
        raise HTTPException(422, "La codificación no coincide con el archivo. Seleccione UTF-8 o Windows-1252.")
    if "\x00" in source:
        raise HTTPException(422, "El archivo contiene caracteres nulos; revise su codificación.")
    csv.field_size_limit(256 * 1024)
    reader = csv.reader(io.StringIO(source, newline=""), delimiter=config["delimiter"], strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error):
        raise HTTPException(422, "No se pudo leer la cabecera del CSV.")
    if not header or any(not field.strip() for field in header):
        raise HTTPException(422, "La cabecera contiene nombres vacíos. Revise el separador seleccionado.")
    if len(header) != len(set(header)):
        raise HTTPException(422, "El CSV contiene columnas con nombres repetidos.")
    if any(key not in header for key in mapping):
        raise HTTPException(422, "El mapeo contiene encabezados que no existen en el CSV.")
    if any(value not in FIELDS[area] and value != "" for value in mapping.values()):
        raise HTTPException(422, "El mapeo apunta a un campo que no corresponde al área.")
    mapped = [mapping.get(field, field.strip().lower()) for field in header]
    expected = set(FIELDS[area])
    recognized = [field for field in mapped if field in expected]
    if len(recognized) != len(set(recognized)):
        raise HTTPException(422, "Dos columnas corresponden al mismo campo. Corrija el mapeo.")
    missing = expected - set(recognized) - {"descripcion"}
    if missing:
        raise HTTPException(422, "Faltan columnas obligatorias: " + ", ".join(sorted(missing)) + ". Puede asignarlas en el mapeo de columnas.")
    messages = []
    extra = [header[i] for i, target in enumerate(mapped) if target not in expected]
    if extra:
        messages.append("Se ignoraron columnas adicionales: " + ", ".join(extra) + ".")
    renamed = [f"{old} → {new}" for old, new in zip(header, mapped) if old != new and new in expected]
    if renamed:
        messages.append("Correspondencia de columnas aplicada: " + "; ".join(renamed) + ".")
    if area == "multas" and "descripcion" not in recognized:
        messages.append("Falta la columna opcional descripcion; se utilizará un valor vacío.")
    rows = []
    empty = 0
    scanned = 0
    try:
        while True:
            start_line = reader.line_num + 1
            try:
                values = next(reader)
            except StopIteration:
                break
            scanned += 1
            if scanned > MAX_ROWS:
                raise HTTPException(413, "El archivo supera el límite de 20 000 filas.")
            if not values or not any(value.strip() for value in values):
                empty += 1
                continue
            data = {field: "" for field in FIELDS[area]}
            for i, field in enumerate(mapped):
                if field in expected:
                    data[field] = values[i] if i < len(values) else ""
            structure_error = None
            if len(values) > len(header):
                structure_error = "La fila contiene más valores que columnas; revise el separador o excluya la fila."
            rows.append({"numero_fila": start_line, "datos": data, "error_estructura": structure_error})
    except csv.Error as exc:
        raise HTTPException(422, f"CSV mal formado cerca de la línea {reader.line_num}: {exc}.")
    if not rows:
        raise HTTPException(422, "El archivo no contiene filas con datos.")
    return rows, messages, empty


def normalize_values(data: dict, area: str, config: dict) -> tuple[dict, list[str], list[str]]:
    """Transforma formatos elegidos a tipos de negocio, sin completar datos."""
    normalized = {}
    errors = []
    warnings = []
    for field in FIELDS[area]:
        value = data.get(field, "")
        raw = "" if value is None else str(value)
        text = raw.strip()
        if raw != text:
            warnings.append(f"{field}: se quitaron espacios al inicio o al final.")
        normalized[field] = text
        if not text:
            if field == "descripcion":
                warnings.append("La multa no tiene descripción.")
            else:
                errors.append(f"{field}: es obligatorio.")
            continue
        if field.startswith("fecha_"):
            pattern, format_string = (
                (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "%Y-%m-%d")
                if config["date_format"] == "iso"
                else (r"[0-9]{2}/[0-9]{2}/[0-9]{4}", "%d/%m/%Y")
            )
            try:
                if not re.fullmatch(pattern, text):
                    raise ValueError
                normalized[field] = datetime.strptime(text, format_string).date()
            except ValueError:
                example = "AAAA-MM-DD" if config["date_format"] == "iso" else "DD/MM/AAAA"
                errors.append(f"{field}: fecha inválida; utilice {example}.")
        elif field in {"monto", "monto_pagado"}:
            decimal_mark = re.escape(config["decimal_separator"])
            if not re.fullmatch(rf"[0-9]+(?:{decimal_mark}[0-9]{{1,2}})?", text):
                errors.append(f"{field}: use un importe positivo con hasta dos decimales, sin símbolos ni separadores de miles.")
                continue
            try:
                amount = Decimal(text.replace(",", "."))
                if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
                    raise InvalidOperation
                normalized[field] = amount
            except InvalidOperation:
                errors.append(f"{field}: importe fuera del rango permitido.")
        elif field == "dni_infractor" and not re.fullmatch(r"[0-9]{8}", text):
            errors.append("dni_infractor: debe contener exactamente ocho dígitos.")
        elif field == "codigo_multa" and not re.fullmatch(r"MUL-[0-9]{14}", text):
            errors.append("codigo_multa: debe tener el formato MUL-00000000000000.")
        elif field == "estado_multa" and text not in {"PENDIENTE", "PARCIAL", "PAGADA"}:
            errors.append("estado_multa: debe ser PENDIENTE, PARCIAL o PAGADA.")
    return normalized, errors, warnings


def spreadsheet_safe(value: object) -> str:
    text = "" if value is None else str(value)
    # Protege también fórmulas precedidas de espacios o caracteres de control.
    if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text
