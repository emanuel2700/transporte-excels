from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.dashboard import router as dashboard_router
from app.db.session import SessionLocal
from app.modules.auth.router import router as auth_router
from app.modules.catalogos.router import router as catalogos_router
from app.modules.multas.router import router as multas_router
from app.modules.pagos.router import router as pagos_router

app = FastAPI(title="Multas y pagos · Prueba de concepto", version="0.1.0", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")

for router in (auth_router, catalogos_router, dashboard_router, multas_router, pagos_router):
    app.include_router(router, prefix="/api")

from app.modules.importaciones.router import router as importaciones_router

app.include_router(importaciones_router, prefix="/api")


@app.get("/api/health", tags=["Estado"])
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_exception(request: Request, error: RequestValidationError):
    # Never echo raw submitted bodies: login contains a demonstration password.
    fields = sorted({".".join(str(x) for x in item["loc"] if x not in ("body", "query", "path")) for item in error.errors()})
    return JSONResponse(status_code=422, content={"detail": "Revisa los campos obligatorios, sus tipos y los campos no permitidos: " + ", ".join(fields)})


@app.exception_handler(IntegrityError)
async def integrity_exception(request: Request, error: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "La operación entra en conflicto con otro registro o una restricción de datos. No se guardaron cambios; actualiza la información y vuelve a intentarlo."})


@app.exception_handler(OperationalError)
async def operational_exception(request: Request, error: OperationalError):
    return JSONResponse(status_code=503, content={"detail": "No se pudo completar la operación con la base de datos. Si estabas confirmando una importación, consulta el estado del lote antes de reintentar."})


@app.exception_handler(Exception)
async def unexpected_exception(request: Request, error: Exception):
    # No devolver cuerpos, parámetros SQL ni secretos en los errores.
    return JSONResponse(status_code=500, content={"detail": "Ocurrió un error inesperado. Si estabas confirmando una importación, consulta el estado del lote antes de reintentar: no se guardan importaciones parcialmente."})
