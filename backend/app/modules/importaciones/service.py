"""Revisión de lotes y confirmación atómica. El router controla commit/rollback."""

import csv
import io
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.importaciones.csv_utils import FIELDS, normalize_values, read_csv, spreadsheet_safe
from app.modules.importaciones.models import FilaImportacion, Importacion
from app.modules.multas.models import Multa
from app.modules.multas.service import create_multa, total_pagado, validate_multa
from app.modules.pagos.models import Pago
from app.modules.pagos.service import create_pago, validate_pago


class ReviewRequired(HTTPException):
    """La revalidación se conserva en borrador; aún no se escribió ningún registro."""


def row_list(db: Session, batch_id: UUID) -> list[FilaImportacion]:
    return list(db.scalars(select(FilaImportacion).where(
        FilaImportacion.importacion_id == batch_id
    ).order_by(FilaImportacion.numero_fila)))


def summary(batch: Importacion, rows: list[FilaImportacion]) -> dict:
    if batch.resumen_final is not None:
        return batch.resumen_final
    result = {"listas": 0, "advertencias": 0, "errores": 0, "excluidas": 0, "vacias": batch.vacias, "importadas": 0}
    categories = {"VALIDA": "listas", "ADVERTENCIA": "advertencias", "ERROR": "errores", "EXCLUIDA": "excluidas", "IMPORTADA": "importadas"}
    for row in rows:
        result[categories[row.resultado]] += 1
    return result


def serialize_batch(db: Session, batch: Importacion, page: int = 1, page_size: int = 50, include_rows: bool = True) -> dict:
    totals = dict(db.execute(select(FilaImportacion.resultado, func.count()).where(
        FilaImportacion.importacion_id == batch.id
    ).group_by(FilaImportacion.resultado)).all())
    calculated = {"listas": totals.get("VALIDA", 0), "advertencias": totals.get("ADVERTENCIA", 0),
                  "errores": totals.get("ERROR", 0), "excluidas": totals.get("EXCLUIDA", 0),
                  "vacias": batch.vacias, "importadas": totals.get("IMPORTADA", 0)}
    selected = list(db.scalars(select(FilaImportacion).where(
        FilaImportacion.importacion_id == batch.id
    ).order_by(FilaImportacion.numero_fila).offset((page - 1) * page_size).limit(page_size))) if include_rows else []
    return {
        "id": str(batch.id), "area": batch.area, "nombre_archivo": batch.nombre_archivo,
        "estado": batch.estado, "creado_por": batch.creado_por, "created_at": batch.created_at,
        "expires_at": batch.expires_at, "confirmed_at": batch.confirmed_at,
        "resumen": batch.resumen_final if batch.resumen_final is not None else calculated,
        "total_filas": sum(totals.values()), "total_original": batch.total_original,
        "page": page, "page_size": page_size, "mensajes": batch.mensajes,
        "configuracion": batch.configuracion,
        "filas": [{
            "id": str(row.id), "numero_fila": row.numero_fila, "datos": row.datos,
            "errores": row.errores, "advertencias": row.advertencias,
            "excluida": row.excluida or row.resultado == "EXCLUIDA", "resultado": row.resultado,
            "registro_id": str(row.registro_id) if row.registro_id else None,
        } for row in selected],
    }


def get_batch(db: Session, batch_id: UUID, lock: bool = False) -> Importacion:
    statement = select(Importacion).where(Importacion.id == batch_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    batch = db.scalar(statement)
    if batch is None:
        raise HTTPException(404, "No se encontró la importación.")
    return batch


def require_draft(batch: Importacion) -> None:
    if batch.estado != "BORRADOR":
        raise HTTPException(409, f"La importación está {batch.estado.lower()} y ya no admite cambios.")
    # La fecha se comprueba también tras adquirir el bloqueo: el borrador pudo
    # vencer mientras esta petición esperaba a otra edición o validación.
    if batch.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(409, "El borrador ha vencido. Actualice el historial para consultar su resumen.")


def purge_draft(db: Session, batch: Importacion, state: str) -> None:
    rows = row_list(db, batch.id)
    batch.resumen_final = summary(batch, rows)
    batch.estado = state
    db.execute(delete(FilaImportacion).where(FilaImportacion.importacion_id == batch.id))
    batch.mensajes = [*batch.mensajes, "Se eliminaron los datos temporales; se conserva el resumen del lote."]
    db.flush()


def expire_drafts(db: Session) -> None:
    # SKIP LOCKED evita interferir con una confirmación que ya obtuvo su bloqueo.
    expired = list(db.scalars(select(Importacion).where(
        Importacion.estado == "BORRADOR", Importacion.expires_at <= datetime.now(timezone.utc)
    ).with_for_update(skip_locked=True)))
    for batch in expired:
        purge_draft(db, batch, "EXPIRADA")


def canonical(value: object) -> str:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return "" if value is None else str(value).strip()


def fingerprint(data: dict, fields: list[str]) -> tuple:
    return tuple(canonical(data.get(field)) for field in fields)


def same_record(data: dict, record: object, area: str) -> bool:
    fields = [field for field in FIELDS[area] if field != "estado_multa"]
    return fingerprint(data, fields) == fingerprint({field: getattr(record, field) for field in fields}, fields)


def error_text(exc: HTTPException) -> str:
    if isinstance(exc.detail, str):
        return exc.detail
    return str(exc.detail)


def validate_batch(db: Session, batch: Importacion) -> dict[UUID, dict]:
    """Revalida todas las filas: editar una puede cambiar duplicados y saldos."""
    rows = row_list(db, batch.id)
    normalized = {}
    groups = defaultdict(list)
    key = "codigo_multa" if batch.area == "multas" else "numero_comprobante"
    for row in rows:
        row.errores = []
        row.advertencias = []
        row.registro_id = None
        if row.excluida:
            row.resultado = "EXCLUIDA"
            row.advertencias = ["Fila excluida por el usuario."]
            continue
        data, errors, warnings = normalize_values(row.datos, batch.area, batch.configuracion)
        if row.error_estructura:
            errors.append(row.error_estructura)
        row.errores = errors
        row.advertencias = warnings
        row.resultado = "ERROR" if errors else "VALIDA"
        normalized[row.id] = data
        if not errors:
            groups[data[key]].append(row)
    # No se elige silenciosamente entre variantes distintas de una misma clave.
    for grouped_rows in groups.values():
        if len(grouped_rows) < 2:
            continue
        fingerprints = {fingerprint(normalized[row.id], FIELDS[batch.area]) for row in grouped_rows}
        if len(fingerprints) > 1:
            for row in grouped_rows:
                row.errores = [*row.errores, f"{key}: se repite en el archivo con datos diferentes. Corrija o excluya las variantes."]
                row.resultado = "ERROR"
        else:
            for row in grouped_rows[1:]:
                row.resultado = "EXCLUIDA"
                row.advertencias = [*row.advertencias, f"Duplicado idéntico de la fila {grouped_rows[0].numero_fila}; no se importará."]

    candidates = [row for row in rows if row.resultado == "VALIDA"]
    codes = {normalized[row.id]["codigo_multa"] for row in candidates}
    fines = {fine.codigo_multa: fine for fine in db.scalars(select(Multa).where(Multa.codigo_multa.in_(codes)))} if codes else {}
    receipts = {normalized[row.id]["numero_comprobante"] for row in candidates} if batch.area == "pagos" else set()
    payments = {payment.numero_comprobante: payment for payment in db.scalars(select(Pago).where(Pago.numero_comprobante.in_(receipts)))} if receipts else {}
    for row in candidates:
        data = normalized[row.id]
        existing = fines.get(data["codigo_multa"]) if batch.area == "multas" else payments.get(data["numero_comprobante"])
        if existing is not None:
            if batch.area == "multas" and existing.eliminada_en is not None:
                row.errores = ["El código pertenece a una multa dada de baja; no se reutilizará ni reactivará."]
                row.resultado = "ERROR"
                continue
            if same_record(data, existing, batch.area):
                row.resultado = "EXCLUIDA"
                status = " (el pago está anulado)" if batch.area == "pagos" and existing.anulado_en else ""
                row.advertencias = [*row.advertencias, f"Registro idéntico ya existente{status}; no se importará de nuevo."]
                if batch.area == "multas":
                    paid = total_pagado(db, existing.codigo_multa)
                    computed = "PENDIENTE" if paid == 0 else "PAGADA" if paid >= existing.monto else "PARCIAL"
                    if data["estado_multa"] != computed:
                        row.advertencias = [*row.advertencias, f"Estado declarado {data['estado_multa']} distinto del calculado {computed}; requiere conciliación."]
                continue
            row.resultado = "ERROR"
            row.errores = [f"{key}: ya existe en la base de datos con datos diferentes; revise el registro existente."]
            continue
        try:
            if batch.area == "multas":
                clean, warnings = validate_multa(db, {k: v for k, v in data.items() if k != "estado_multa"})
                if data["estado_multa"] != "PENDIENTE":
                    warnings = [*warnings, f"El CSV declara {data['estado_multa']}, pero sin pagos asociados el estado calculado será PENDIENTE. Importe los pagos y concilie después."]
            else:
                clean, warnings = validate_pago(db, data, check_balance=False)
            normalized[row.id] = clean
            row.advertencias = list(dict.fromkeys([*row.advertencias, *warnings]))
        except HTTPException as exc:
            row.errores = [*row.errores, error_text(exc)]
            row.resultado = "ERROR"

    # Se valida la suma del grupo completo, sin decidir por el orden del archivo.
    if batch.area == "pagos":
        by_fine = defaultdict(list)
        for row in rows:
            if row.resultado == "VALIDA":
                by_fine[normalized[row.id]["codigo_multa"]].append(row)
        for code, grouped_rows in by_fine.items():
            fine = fines.get(code)
            if fine is None:
                continue  # validate_pago ya informa la referencia inexistente.
            balance = fine.monto - total_pagado(db, code)
            total = sum((normalized[row.id]["monto_pagado"] for row in grouped_rows), Decimal("0"))
            if total > balance:
                for row in grouped_rows:
                    row.errores = [*row.errores, f"Los pagos seleccionados para {code} suman {total:.2f} y superan el saldo {balance:.2f}. Corrija o excluya filas del grupo."]
                    row.resultado = "ERROR"
            # Una posible repetición con comprobantes diferentes requiere revisión.
            possible_duplicates = defaultdict(list)
            for row in grouped_rows:
                data = normalized[row.id]
                possible_duplicates[(data["fecha_pago"], data["monto_pagado"])].append(row)
                prior = db.scalar(select(Pago.id).where(
                    Pago.codigo_multa == code, Pago.fecha_pago == data["fecha_pago"],
                    Pago.monto_pagado == data["monto_pagado"], Pago.anulado_en.is_(None)
                ).limit(1))
                if prior is not None:
                    row.advertencias = [*row.advertencias, "Ya existe un pago con la misma multa, fecha e importe y otro comprobante. Revise si es un duplicado."]
            for same in possible_duplicates.values():
                if len(same) > 1:
                    for row in same:
                        row.advertencias = [*row.advertencias, "El archivo tiene otros pagos de esta multa con la misma fecha e importe y diferente comprobante."]
    for row in rows:
        if row.resultado == "VALIDA" and row.advertencias:
            row.resultado = "ADVERTENCIA"
    db.flush()
    return normalized


def create_batch(db: Session, content: bytes, filename: str, area: str, config: dict, mapping: dict, username: str) -> Importacion:
    parsed, messages, empty = read_csv(content, area, config, mapping)
    batch = Importacion(
        area=area, nombre_archivo=filename.replace("\\", "/").split("/")[-1][:255],
        creado_por=username, configuracion=config, mensajes=messages, vacias=empty, total_original=len(parsed),
    )
    db.add(batch)
    db.flush()
    for item in parsed:
        db.add(FilaImportacion(
            importacion_id=batch.id, numero_fila=item["numero_fila"], datos_originales=item["datos"].copy(),
            datos=item["datos"], error_estructura=item["error_estructura"],
        ))
    db.flush()
    validate_batch(db, batch)
    return batch


def edit_row(db: Session, batch: Importacion, row_id: UUID, data: dict | None, excluded: bool | None) -> None:
    row = db.scalar(select(FilaImportacion).where(
        FilaImportacion.id == row_id, FilaImportacion.importacion_id == batch.id
    ))
    if row is None:
        raise HTTPException(404, "No se encontró la fila en esta importación.")
    if data is not None:
        unknown = set(data) - set(FIELDS[batch.area])
        if unknown:
            raise HTTPException(422, "Campos desconocidos: " + ", ".join(sorted(unknown)))
        if any(isinstance(value, (dict, list, bool)) for value in data.values()):
            raise HTTPException(422, "Los campos de una fila deben ser valores de texto.")
        if any(len(str(value)) > 256 * 1024 for value in data.values()):
            raise HTTPException(422, "Un campo excede el tamaño máximo permitido.")
        row.datos = {**row.datos, **{key: "" if value is None else str(value) for key, value in data.items()}}
    if excluded is not None:
        row.excluida = excluded
    db.flush()
    validate_batch(db, batch)


def confirm_batch(db: Session, batch: Importacion, username: str, accept_warnings: bool) -> None:
    if batch.estado == "CONFIRMADA":
        return  # Idempotencia: mismo lote, mismo resultado, incluso tras perder conexión.
    require_draft(batch)
    before = row_list(db, batch.id)
    expected = {row.id for row in before if row.resultado in {"VALIDA", "ADVERTENCIA"}}
    warnings_before = {row.id: row.advertencias[:] for row in before}
    codes = sorted({str(row.datos.get("codigo_multa", "")).strip() for row in before if row.id in expected})
    if codes:
        # Orden estable de bloqueo para evitar interbloqueos entre lotes.
        list(db.scalars(select(Multa).where(Multa.codigo_multa.in_(codes)).order_by(Multa.codigo_multa)
                        .with_for_update().execution_options(populate_existing=True)))
    normalized = validate_batch(db, batch)
    rows = row_list(db, batch.id)
    eligible = [row for row in rows if row.resultado in {"VALIDA", "ADVERTENCIA"}]
    actual = {row.id for row in eligible}
    changed_warnings = any(warnings_before.get(row.id) != row.advertencias for row in eligible)
    if actual != expected or changed_warnings:
        raise ReviewRequired(409, "La información cambió desde la revisión. No se importó ninguna fila. Revise los resultados actualizados y vuelva a confirmar.")
    if not eligible:
        raise ReviewRequired(422, "No hay filas válidas para importar. Corrija los errores o revise las exclusiones.")
    if (any(row.advertencias for row in eligible) or batch.mensajes) and not accept_warnings:
        raise ReviewRequired(422, "Debe aceptar las advertencias antes de confirmar la importación.")
    for row in eligible:
        create = create_multa if batch.area == "multas" else create_pago
        record = create(db, normalized[row.id], username)
        row.registro_id = record.id
        row.resultado = "IMPORTADA"
    batch.estado = "CONFIRMADA"
    batch.confirmed_at = datetime.now(timezone.utc)
    batch.resumen_final = summary(batch, rows)
    db.flush()


def report_csv(db: Session, batch: Importacion) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    fields = FIELDS[batch.area]
    writer.writerow(["numero_fila", *fields, "resultado", "errores", "advertencias", "registro_id"])
    for row in row_list(db, batch.id):
        values = [row.numero_fila, *[row.datos.get(field, "") for field in fields], row.resultado,
                  " | ".join(row.errores), " | ".join(row.advertencias), row.registro_id]
        writer.writerow([spreadsheet_safe(value) for value in values])
    return "\ufeff" + output.getvalue()
