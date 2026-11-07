import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.importaciones.csv_utils import MAX_BYTES
from app.modules.importaciones.models import Importacion
from app.modules.importaciones.service import (
    ReviewRequired, confirm_batch, create_batch, edit_row, expire_drafts, get_batch,
    purge_draft, report_csv, require_draft, serialize_batch, validate_batch,
)

router = APIRouter(prefix="/importaciones", tags=["Importaciones"])


class RowEdit(BaseModel):
    datos: dict | None = None
    excluida: bool | None = None
    model_config = ConfigDict(extra="forbid")


class Confirmation(BaseModel):
    aceptar_advertencias: bool = False
    model_config = ConfigDict(extra="forbid")


def maintenance(db: Session) -> None:
    expire_drafts(db)
    db.commit()


def storage_error(db: Session, exc: SQLAlchemyError) -> HTTPException:
    db.rollback()
    if isinstance(exc, IntegrityError):
        return HTTPException(409, "Se detectó un conflicto al guardar. Se revirtió el intento completo; vuelva a validar el lote antes de confirmar.")
    return HTTPException(503, "No se pudo verificar el resultado del guardado. Consulte el estado de esta importación antes de reintentar; el mismo lote no se importará dos veces.")


@router.post("", status_code=201)
def upload(
    file: UploadFile = File(...), area: str = Form(...),
    encoding: str = Form("utf-8-sig"), delimiter: str = Form(","),
    date_format: str = Form("iso"), decimal_separator: str = Form("."),
    column_mapping: str = Form("{}"),
    db: Session = Depends(get_db), username: str = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "Seleccione un archivo con extensión .csv.")
    try:
        mapping = json.loads(column_mapping)
        if not isinstance(mapping, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items()):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(422, "El mapeo debe ser un objeto JSON de encabezado original a campo esperado.")
    # Las consultas síncronas se ejecutan en el pool de FastAPI, sin bloquear su loop.
    content = file.file.read(MAX_BYTES + 1)
    config = {"encoding": encoding, "delimiter": "\t" if delimiter == "tab" else delimiter,
              "date_format": date_format, "decimal_separator": decimal_separator}
    try:
        maintenance(db)
        batch = create_batch(db, content, file.filename, area, config, mapping, username)
        db.commit()
        return serialize_batch(db, batch)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        raise storage_error(db, exc)


@router.get("")
def list_batches(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db), username: str = Depends(get_current_user),
):
    maintenance(db)
    total = db.scalar(select(func.count()).select_from(Importacion))
    batches = db.scalars(select(Importacion).order_by(Importacion.created_at.desc())
                         .offset((page - 1) * page_size).limit(page_size))
    return {"items": [serialize_batch(db, batch, include_rows=False) for batch in batches],
            "total": total, "page": page, "page_size": page_size}


@router.get("/{batch_id}")
def detail(
    batch_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db), username: str = Depends(get_current_user),
):
    maintenance(db)
    return serialize_batch(db, get_batch(db, batch_id), page, page_size)


@router.patch("/{batch_id}/filas/{row_id}")
def update_row(
    batch_id: UUID, row_id: UUID, payload: RowEdit,
    db: Session = Depends(get_db), username: str = Depends(get_current_user),
):
    try:
        maintenance(db)
        batch = get_batch(db, batch_id, lock=True)
        require_draft(batch)
        edit_row(db, batch, row_id, payload.datos, payload.excluida)
        db.commit()
        return serialize_batch(db, batch)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        raise storage_error(db, exc)


@router.post("/{batch_id}/validar")
def revalidate(
    batch_id: UUID, db: Session = Depends(get_db), username: str = Depends(get_current_user),
):
    try:
        maintenance(db)
        batch = get_batch(db, batch_id, lock=True)
        require_draft(batch)
        validate_batch(db, batch)
        db.commit()
        return serialize_batch(db, batch)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        raise storage_error(db, exc)


@router.post("/{batch_id}/confirmar")
def confirm(
    batch_id: UUID, payload: Confirmation,
    db: Session = Depends(get_db), username: str = Depends(get_current_user),
):
    try:
        maintenance(db)
        batch = get_batch(db, batch_id, lock=True)
        confirm_batch(db, batch, username, payload.aceptar_advertencias)
        db.commit()
        return serialize_batch(db, batch)
    except ReviewRequired:
        # No se han llamado servicios de alta. Conservamos la revalidación actualizada.
        try:
            db.commit()
        except SQLAlchemyError as exc:
            raise storage_error(db, exc)
        raise
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        raise storage_error(db, exc)


@router.post("/{batch_id}/cancelar")
def cancel(
    batch_id: UUID, db: Session = Depends(get_db), username: str = Depends(get_current_user),
):
    try:
        maintenance(db)
        batch = get_batch(db, batch_id, lock=True)
        if batch.estado == "CANCELADA":
            return serialize_batch(db, batch)
        require_draft(batch)
        purge_draft(db, batch, "CANCELADA")
        db.commit()
        return serialize_batch(db, batch)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        raise storage_error(db, exc)


@router.get("/{batch_id}/reporte")
def report(
    batch_id: UUID, db: Session = Depends(get_db), username: str = Depends(get_current_user),
):
    maintenance(db)
    batch = get_batch(db, batch_id)
    return Response(report_csv(db, batch), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="importacion-{batch.id}.csv"'})
