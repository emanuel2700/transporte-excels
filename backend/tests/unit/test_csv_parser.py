from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.modules.importaciones.csv_utils import FIELDS, normalize_values, read_csv, spreadsheet_safe


CONFIG = {"encoding": "utf-8-sig", "delimiter": ",", "date_format": "iso", "decimal_separator": "."}
FINE = {
    "codigo_multa": "MUL-00000000000001", "dni_infractor": "01234567",
    "tipo_infraccion": "DOCUMENTACION", "descripcion": "Control de tránsito",
    "fecha_infraccion": "2026-01-01", "lugar_infraccion": "Lima", "monto": "100.00",
    "estado_multa": "PENDIENTE", "fecha_vencimiento": "2026-02-01", "fecha_registro": "2026-01-02",
}


def source(fields=None, values=None, separator=","):
    fields = fields or FIELDS["multas"]
    values = values or FINE
    return separator.join(fields) + "\n" + separator.join(values.get(field, "") for field in fields) + "\n"


def test_bom_empty_rows_and_leading_zero_dni():
    rows, messages, empty = read_csv(("\ufeff" + source() + "\n,,,\n").encode(), "multas", CONFIG, {})
    assert empty == 2
    assert rows[0]["numero_fila"] == 2
    normalized, errors, warnings = normalize_values(rows[0]["datos"], "multas", CONFIG)
    assert not errors and not warnings and not messages
    assert normalized["dni_infractor"] == "01234567"
    assert normalized["monto"] == Decimal("100")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0", "1.001", "1,000.00", "$10", "1e3", "10000000000.00"])
def test_money_is_never_guessed_or_rounded(value):
    _, errors, _ = normalize_values({**FINE, "monto": value}, "multas", CONFIG)
    assert any("monto" in error for error in errors)


@pytest.mark.parametrize("value", ["2026-02-30", "01/02/2026", "2026-1-2", ""])
def test_invalid_dates_are_row_errors(value):
    _, errors, _ = normalize_values({**FINE, "fecha_registro": value}, "multas", CONFIG)
    assert any("fecha_registro" in error for error in errors)


def test_explicit_legacy_format_preserves_spanish_characters_and_amount():
    config = {**CONFIG, "encoding": "cp1252", "delimiter": ";", "date_format": "dmy", "decimal_separator": ","}
    legacy = {**FINE, "monto": "123,45", "fecha_infraccion": "01/01/2026",
              "fecha_registro": "02/01/2026", "fecha_vencimiento": "01/02/2026"}
    rows, _, _ = read_csv(source(values=legacy, separator=";").encode("cp1252"), "multas", config, {})
    normalized, errors, _ = normalize_values(rows[0]["datos"], "multas", config)
    assert not errors
    assert normalized["monto"] == Decimal("123.45")
    assert normalized["descripcion"] == "Control de tránsito"


def test_mismatching_encoding_is_an_explicit_error():
    with pytest.raises(HTTPException, match="codificación"):
        read_csv(source().encode("cp1252"), "multas", CONFIG, {})


def test_mapping_missing_column_and_extra_column():
    renamed = source().replace("codigo_multa", "Código", 1)
    with pytest.raises(HTTPException, match="Faltan columnas"):
        read_csv(renamed.encode(), "multas", CONFIG, {})
    rows, warnings, _ = read_csv(renamed.encode(), "multas", CONFIG, {"Código": "codigo_multa"})
    assert rows[0]["datos"]["codigo_multa"] == FINE["codigo_multa"]
    assert any("Correspondencia" in message for message in warnings)
    fields = [*FIELDS["multas"], "interno"]
    _, warnings, _ = read_csv(source(fields=fields, values={**FINE, "interno": "ignorado"}).encode(), "multas", CONFIG, {})
    assert any("adicionales" in message for message in warnings)


def test_duplicate_mapping_is_rejected():
    with pytest.raises(HTTPException, match="mismo campo"):
        read_csv(source().encode(), "multas", CONFIG, {"descripcion": "dni_infractor"})


def test_missing_optional_description_is_warning():
    fields = [field for field in FIELDS["multas"] if field != "descripcion"]
    rows, warnings, _ = read_csv(source(fields=fields).encode(), "multas", CONFIG, {})
    assert rows[0]["datos"]["descripcion"] == ""
    assert any("opcional" in message for message in warnings)


def test_broken_quoting_does_not_return_partial_rows():
    malformed = source() + '"comilla sin cerrar\n'
    with pytest.raises(HTTPException, match="CSV mal formado"):
        read_csv(malformed.encode(), "multas", CONFIG, {})


@pytest.mark.parametrize("value", ["=SUM(A1:A2)", "  +CMD()", "-1+1", "@SUM(A1)", "\tformula"])
def test_download_escapes_spreadsheet_formulas(value):
    assert spreadsheet_safe(value) == "'" + value
