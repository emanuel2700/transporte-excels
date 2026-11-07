# Transporte · Multas y Cobranzas

Prueba de concepto para registrar multas y pagos, consultar saldos e importar CSV mediante una revisión previa. Incluye una interfaz React + TypeScript, una API FastAPI y PostgreSQL, ejecutados con Docker Compose.

El acceso es **simulado**: acepta cualquier usuario y contraseña no vacíos. El usuario declarado se conserva en la sesión y se registra en las altas, modificaciones, bajas, anulaciones e importaciones. La contraseña no se guarda. Esto sirve para demostrar la trazabilidad; no verifica la identidad ni implementa roles. Seleccionar un área solo cambia el módulo visible.

## Requisitos

- Git, si se va a clonar o versionar el proyecto.
- Docker Engine o Docker Desktop **en ejecución**, con Docker Compose v2 (`docker compose`).
- Conexión a Internet para descargar las imágenes y dependencias en la primera construcción.
- Puerto local `8080` disponible, o uno alternativo configurado en `.env`.
- Navegador actualizado.

**No es necesario instalar Python, Node.js ni PostgreSQL en el equipo para usar Docker.** Para desarrollo fuera de Docker: Python 3.12, uv, Node.js 22.12 o superior y npm.

Comprueba la instalación:

```bash
docker --version
docker compose version
docker info
```

## Instalación y ejecución

### 1. Obtener el proyecto

```bash
git clone https://github.com/emanuel2700/transporte-excels.git
cd transporte-excels
```

Si ya estás trabajando en esta carpeta, utiliza la copia existente.

### 2. Preparar la configuración local

Si no tienes un `.env`, copia el ejemplo:

```bash
cp .env.example .env
```

Edita `.env`:

| Variable | Uso |
| --- | --- |
| `WEB_PORT` | Puerto del navegador; predeterminado `8080` |
| `POSTGRES_DB` | Nombre de la base; predeterminado `transporte` |
| `POSTGRES_USER` | Usuario exclusivo de esta base |
| `POSTGRES_PASSWORD` | Contraseña de la base local |
| `SESSION_SECRET` | Cadena aleatoria larga para firmar la sesión de demostración |
| `SESSION_COOKIE_SECURE` | `false` para HTTP local; `true` solo con HTTPS |

Para esta configuración, usa letras, números y guiones en las credenciales de PostgreSQL: se incorporan a una URL de conexión. No uses los valores de demostración para un despliegue compartido. Puedes generar una clave de sesión con `openssl rand -hex 32` si tienes OpenSSL.

`.env` está excluido de Git. Si ya existe, conserva su configuración. Cambiar las credenciales en `.env` **no modifica** las credenciales de un volumen PostgreSQL ya inicializado.

### 3. Construir e iniciar

```bash
docker compose up --build -d
docker compose ps
```

En el primer inicio se descargan las imágenes, se construyen el frontend y el backend, se crea la base y se aplican las migraciones de Alembic. Se cargan los catálogos de demostración, pero no multas ni pagos.

Espera a que los tres servicios estén saludables. Si alguno no inicia:

```bash
docker compose logs --tail=100 api web db
```

### 4. Abrir la aplicación

- Aplicación: **http://localhost:8080**
- Documentación interactiva de la API: **http://localhost:8080/api/docs**
- Estado del backend: **http://localhost:8080/api/health**

Si cambiaste `WEB_PORT`, utiliza ese puerto. Ingresa, por ejemplo, usuario `operador_demo` y cualquier contraseña no vacía. Inicia sesión en la aplicación antes de probar endpoints protegidos desde la documentación.

## Probar el flujo completo

1. Inicia sesión y abre el módulo de Multas.
2. En Importación, selecciona **Multas** y carga `examples/csv/multas.csv` con UTF-8, coma, fechas ISO y decimal con punto.
3. Revisa las filas y confirma. Antes de confirmar, no aparecerán multas en las tablas definitivas.
4. Selecciona **Pagos** y carga `examples/csv/pagos.csv` con la misma configuración.
5. Confirma y consulta las multas: la primera tendrá un pago parcial de S/ 100 sobre S/ 300; la segunda estará pagada, S/ 150 sobre S/ 150.
6. Carga `examples/csv/multas_con_errores.csv` para revisar advertencias, corregir campos, excluir filas y revalidar. También puedes cancelar el lote.
7. Vuelve a cargar un archivo ya importado: los duplicados idénticos se excluyen y no se crean registros repetidos.
8. Cierra sesión e ingresa con otro nombre. Los siguientes cambios quedarán asociados al nuevo usuario declarado.

Los archivos de ejemplo contienen datos ficticios. No se deben subir CSV reales, documentos personales ni respaldos a Git.

## Desplegar el frontend en Vercel

El frontend usa rutas relativas `/api/...`. `frontend/vercel.json` reenvía esas peticiones a `https://transporte-excels.onrender.com`, de modo que el navegador mantiene un mismo origen para la interfaz y la API. Esto permite usar la sesión por cookie sin abrir CORS en el backend. Las respuestas de la API llevan `Cache-Control: no-store` porque incluyen información de los registros.

1. En Vercel, importa este repositorio desde GitHub y selecciona la rama `master`.
2. Configura **Root Directory** en `frontend` y usa el preset **Vite**.
3. Vercel detectará `npm run build` y la carpeta de salida `dist`; confirma esos valores si te los solicita.
4. Despliega y revisa `https://TU-PROYECTO.vercel.app/api/health`. La respuesta debe ser `{"status":"ok"}`.

Si cambia el dominio público de Render, actualiza el destino de `frontend/vercel.json` y vuelve a desplegar. En Render mantén `SESSION_COOKIE_SECURE=true` para que el navegador acepte la cookie de sesión en HTTPS.

## Funcionalidades y reglas

- Listados paginados de multas y pagos, búsqueda y filtros.
- Creación, detalle y edición; baja lógica de multas sin pagos y anulación de pagos con motivo.
- UUID como clave primaria de todas las tablas; código de multa único y relación de pagos con la multa y el DNI.
- `estado_multa` calculado: `PENDIENTE`, `PARCIAL` o `PAGADA`. El vencimiento se muestra aparte. No se edita manualmente.
- Pagos parciales, con moneda única asumida: soles. No se admiten sobrepagos, intereses, descuentos ni devoluciones en esta versión.
- Comprobante único en toda la empresa, incluso después de anular el pago.
- DNI como texto de exactamente ocho dígitos ASCII; conserva ceros iniciales.
- Código con formato `MUL-` seguido de catorce dígitos.
- Importes positivos y finitos de hasta dos decimales, sin redondeo silencioso.
- Fechas de negocio según `America/Lima`; fecha de infracción no posterior al registro, vencimiento no anterior al registro, y pago no anterior a la infracción ni futuro.
- Historial de cambios con usuario declarado, fecha y detalle. La contraseña no se registra.

Un pago para una multa inexistente o con DNI distinto se rechaza. Para cambiar el monto o la multa de un pago se anula y registra nuevamente con un comprobante distinto; fecha, método y comprobante sí pueden corregirse mientras esté vigente. No se elimina físicamente el historial.

Los catálogos iniciales son demostrativos y no representan una norma oficial:

- Infracciones: `EXCESO_VELOCIDAD`, `ESTACIONAMIENTO_INDEBIDO`, `SEMAFORO_ROJO`, `DOCUMENTACION`.
- Métodos: `EFECTIVO`, `TRANSFERENCIA`, `TARJETA`, `YAPE`, `PLIN`.

## Importación de CSV

La importación acepta hasta **10 MB y 20 000 filas** por archivo. Permite elegir UTF-8 (con o sin BOM) o Windows-1252, separador, formato de fechas y separador decimal. Los encabezados inesperados pueden mapearse explícitamente a los campos esperados. Columnas adicionales producen advertencias; las obligatorias faltantes bloquean la lectura. `descripcion` es opcional.

Cada lote mantiene un borrador con sus filas, errores y advertencias. Puedes corregir, excluir o recuperar filas, y revalidar antes de confirmar. Las categorías del resumen son disjuntas: listas sin advertencias, listas con advertencias, con errores y excluidas. Las filas vacías se contabilizan por separado.

La confirmación procesa **todas las filas elegibles mostradas**, dejando fuera errores y exclusiones. Antes de insertar vuelve a validar los datos y los saldos. Los registros definitivos y el resultado del lote se guardan juntos en una única transacción: si falla el guardado, no queda una parte importada. Los reintentos del mismo lote son idempotentes.

- Cancelar un borrador no crea registros y purga sus filas temporales.
- Los borradores vencen a las 24 horas; su limpieza se ejecuta al acceder al módulo de importaciones.
- Si la conexión se pierde durante la confirmación, consulta el lote en el historial para conocer el resultado antes de intentar otra carga.
- Una importación confirmada no se cancela; sus registros se corrigen con las operaciones de cada módulo.
- El `estado_multa` del CSV se contrasta con el estado calculado. Las diferencias son advertencias para conciliación: nunca se crean pagos ficticios.
- Los duplicados idénticos se excluyen; las claves repetidas con datos distintos generan errores. La importación no hace actualizaciones automáticas.
- El reporte descargable contiene el resultado por fila y protege las celdas que podrían interpretarse como fórmulas en hojas de cálculo.

Primero importa multas y después pagos. Consulta [las reglas de negocio](docs/reglas-negocio.md) y [el contrato de la API](docs/api-contract.md) para más detalles.

## Docker y persistencia

El proyecto Compose se llama `transporte-excels`. Crea su propia red y el volumen `transporte-excels_postgres_data`. No utiliza ni modifica los contenedores `postgres`, `gestion_reclamos_db`, `redis-local` ni sus volúmenes.

Solo se publica la web en `127.0.0.1:8080`. PostgreSQL y FastAPI se comunican dentro de la red de Docker; no ocupan el puerto `5432` del equipo. El arranque espera a que PostgreSQL esté saludable y a que la API haya aplicado las migraciones. Referencias: [orden de arranque de Compose](https://docs.docker.com/compose/how-tos/startup-order/) y [FastAPI en Docker](https://fastapi.tiangolo.com/deployment/docker/).

Para detener manteniendo todos los datos:

```bash
docker compose stop
```

Para reanudar:

```bash
docker compose up -d
```

Para retirar los contenedores y la red conservando el volumen:

```bash
docker compose down
```

**No añadas `-v` a `down` si quieres conservar los datos.** No es necesario borrar volúmenes para reconstruir la aplicación.

Después de cambiar el código:

```bash
docker compose up --build -d
```

Para obtener un respaldo local (Linux/macOS):

```bash
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/transporte.dump
```

`backups/` está excluido de Git. La restauración debe realizarse sobre una base elegida expresamente, evitando sobrescribir datos por accidente.

## Pruebas automatizadas

Las pruebas de integración utilizan **PostgreSQL real en otra base**, `transporte_test`, sobre almacenamiento efímero. No limpian ni utilizan la base de la aplicación.

```bash
docker compose -f compose.yaml -f compose.test.yaml --profile test run --build --rm tests
```

Se comprueban validaciones, sesión y usuario, referencias de pagos, saldos y concurrencia, anulaciones, duplicados, corrección de filas, cancelación, reintentos y reversión completa de importaciones ante un error simulado de guardado.

Al terminar puedes detener únicamente la base de pruebas:

```bash
docker compose -f compose.yaml -f compose.test.yaml --profile test stop db-test
```

Para comprobar TypeScript y la construcción del frontend sin instalar Node localmente:

```bash
docker compose build web
```

### Pruebas en navegador (opcional)

Requieren Node.js y npm en el equipo. El archivo `compose.e2e.yaml` levanta una instalación desechable en el puerto `18080`, con otra base efímera. Los recorridos usan datos ficticios y no acceden a la instalación de `8080`.

Desde la raíz del repositorio:

```bash
docker compose build api web
docker compose -f compose.e2e.yaml up -d --wait
cd tests/e2e
npm ci
npx playwright install chromium
npm test
cd ../..
docker compose -f compose.e2e.yaml down
```

Los recorridos comprueban registro manual, pagos parciales y anulación; corrección y confirmación de CSV; y navegación móvil con cancelación. Capturas y trazas se generan en `tests/e2e/test-results/`, excluido de Git. Retira el entorno desechable después de cada ejecución completa para que el siguiente ensayo comience sin registros anteriores. Si ya tienes Chromium, puedes indicar su ruta con `PLAYWRIGHT_EXECUTABLE_PATH` en lugar de descargar otro navegador.

## Organización del repositorio

```text
frontend/          React, TypeScript, Vite, estilos y Nginx
backend/app/       API, módulos y validaciones compartidas
backend/migrations/ Migraciones Alembic y catálogos iniciales
backend/tests/     Pruebas de negocio e integración
tests/e2e/         Recorridos Playwright de escritorio y móvil
docs/              Arquitectura, reglas y contrato de API
examples/csv/      Archivos ficticios para la demostración
compose.yaml       Ejecución local con datos persistentes
compose.test.yaml  Entorno adicional de pruebas aisladas
compose.e2e.yaml   Instalación efímera para pruebas en navegador
.env.example       Variables de ejemplo, sin secretos reales
```

Las versiones de las dependencias quedan fijadas en `frontend/package-lock.json` y `backend/uv.lock`. Las modificaciones del esquema deben acompañarse de una migración, no de cambios manuales sobre la base.

## Git

Se versionan código, migraciones, pruebas, documentación y ejemplos ficticios. `.gitignore` excluye `.env`, dependencias, compilados, CSV reales, respaldos y archivos locales del entorno.

Antes de un commit:

```bash
git status --short
git diff
```

Revisa también los archivos nuevos: `git diff` no los muestra hasta agregarlos. Confirma que no haya datos reales ni secretos. El remoto previsto es `https://github.com/emanuel2700/transporte-excels.git`.

## Alcance de esta versión

La aplicación es una prueba de concepto local con acceso simulado. Los nombres de usuario no prueban identidad. Los catálogos y reglas de comprobantes deben validarse con la empresa antes de migrar registros reales. Un despliegue compartido requiere decidir autenticación real, HTTPS, respaldo y operación; esta configuración publica únicamente en el equipo local.
