import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def application():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Configura TEST_DATABASE_URL con una base exclusiva cuyo nombre termine en _test")
    from sqlalchemy.engine import make_url
    if not (make_url(url).database or "").endswith("_test"):
        raise RuntimeError("Las pruebas solo pueden limpiar bases cuyo nombre termine en _test")
    os.environ["DATABASE_URL"] = url
    os.environ["SESSION_SECRET"] = "secreto-solo-para-pruebas-transporte-excels"
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    from alembic import command
    from alembic.config import Config
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    return app


@pytest.fixture
def client(application):
    from app.db.base import Base
    from app.db.session import engine
    from fastapi.testclient import TestClient
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name not in {"tipos_infraccion", "metodos_pago"}:
                connection.execute(table.delete())
    with TestClient(application, raise_server_exceptions=False) as test_client:
        login = test_client.post("/api/auth/login", json={"username": "operador_demo", "password": "cualquiera"})
        assert login.status_code == 200, login.text
        yield test_client


@pytest.fixture
def multa_data():
    return {
        "codigo_multa": "MUL-00000000000001",
        "dni_infractor": "01234567",
        "tipo_infraccion": "EXCESO_VELOCIDAD",
        "descripcion": "Datos ficticios de prueba",
        "fecha_infraccion": "2025-01-01",
        "lugar_infraccion": "Avenida de prueba",
        "monto": "100.00",
        "fecha_vencimiento": "2025-02-01",
        "fecha_registro": "2025-01-02",
    }


@pytest.fixture
def pago_data():
    return {
        "codigo_multa": "MUL-00000000000001",
        "dni_infractor": "01234567",
        "fecha_pago": "2025-01-03",
        "monto_pagado": "40.00",
        "metodo_pago": "EFECTIVO",
        "numero_comprobante": "TEST-001",
    }
