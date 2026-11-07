# Contrato de la prueba de concepto

API bajo `/api`. Importes como cadenas decimales, fechas `YYYY-MM-DD`, UUID como cadenas.
Errores de negocio: `{ "detail": "mensaje en español" }`. Paginación: `{items, total, page, page_size}`.
Todas las rutas salvo login y health requieren sesión de demostración en cookie HttpOnly `transporte_session`.

## Sesión y catálogos
- `POST /auth/login` `{username,password}` → `{username}`; cualquier combinación no vacía. Nunca guardar contraseña.
- `GET /auth/me` → `{username}`; `POST /auth/logout` → 204.
- `GET /catalogos` → `{tipos_infraccion:[{codigo,nombre}],metodos_pago:[{codigo,nombre}]}`.
- `GET /dashboard` → `{multas,total_multas,total_pagado,saldo_pendiente,pagos,multas_vencidas}` (contadores numéricos e importes string).

## Multas y pagos
- `GET /multas?q=&estado=&tipo_infraccion=&desde=&hasta=&page=1&page_size=20`.
- `POST /multas`, `GET /multas/{id}`, `PATCH /multas/{id}`, `DELETE /multas/{id}` con `{motivo}`.
- Multa entrada: codigo_multa,dni_infractor,tipo_infraccion,descripcion,fecha_infraccion,lugar_infraccion,monto,fecha_vencimiento,fecha_registro.
- Multa salida añade id,estado_multa calculado (`PENDIENTE/PARCIAL/PAGADA`),total_pagado,saldo,vencida,creado_por,actualizado_por,created_at,updated_at,eliminada_en; detalle añade `pagos` y `historial`.
- `GET /pagos?q=&metodo_pago=&desde=&hasta=&incluir_anulados=false&page=1&page_size=20`.
- `POST /pagos`, `GET /pagos/{id}`, `PATCH /pagos/{id}`, `DELETE /pagos/{id}` con `{motivo}` (anulación).
- Pago entrada: codigo_multa,dni_infractor,fecha_pago,monto_pagado,metodo_pago,numero_comprobante.
- Pago salida añade id,anulado_en,motivo_anulacion,creado_por,actualizado_por,created_at,updated_at; detalle añade `historial`.
- Catálogos iniciales demo: infracciones `EXCESO_VELOCIDAD`, `ESTACIONAMIENTO_INDEBIDO`, `SEMAFORO_ROJO`, `DOCUMENTACION`; métodos `EFECTIVO`, `TRANSFERENCIA`, `TARJETA`, `YAPE`, `PLIN`. No son catálogo normativo.

## Importaciones
- `POST /importaciones` multipart `file`, `area` (`multas/pagos`), `encoding` (`utf-8-sig/cp1252`), `delimiter` (`,/;/tab`), `date_format` (`iso/dmy`), `decimal_separator` (`./,`), opcional `column_mapping` JSON objeto encabezado original → campo esperado. → detalle del lote.
- `GET /importaciones?page=1&page_size=20` → lista paginada.
- `GET /importaciones/{id}?page=1&page_size=50` → detalle con filas paginadas.
- `PATCH /importaciones/{id}/filas/{row_id}` `{datos: {...},excluida?:bool}` → detalle; cualquier sesión de demostración puede editar un lote en estado borrador.
- `POST /importaciones/{id}/validar` → detalle.
- `POST /importaciones/{id}/confirmar` `{aceptar_advertencias:bool}` → detalle. Confirma todas las filas elegibles, omite errores/exclusiones explícitamente; la identidad del lote hace idempotente la confirmación.
- `POST /importaciones/{id}/cancelar` → detalle.
- `GET /importaciones/{id}/reporte` → CSV de resultados; proteger fórmulas de hoja de cálculo.
- Lote: `{id,area,nombre_archivo,estado,creado_por,created_at,expires_at,resumen,filas,total_filas,page,page_size,mensajes}`.
- Estado lote `BORRADOR/CONFIRMADA/CANCELADA/EXPIRADA`.
- Resumen `{listas,advertencias,errores,excluidas,vacias,importadas}`. Listas sin advertencias y advertencias importables son categorías disjuntas.
- Fila `{id,numero_fila,datos,errores:[string],advertencias:[string],excluida,resultado,registro_id}`. Resultado `VALIDA/ADVERTENCIA/ERROR/EXCLUIDA/IMPORTADA`.
- Historial: lista de `{id,accion,usuario,created_at,detalle}`.
- No hay permisos por área ni por propietario del lote. Cualquier usuario de demostración puede revisar, editar, validar, confirmar o cancelar borradores. `creado_por` del lote conserva a quien lo cargó; los registros definitivos y su auditoría llevan al usuario de la sesión que confirma.

## Reglas transversales
- Fecha local del negocio America/Lima. Código `^MUL-[0-9]{14}$`; DNI `^[0-9]{8}$`.
- Importes finitos >0, máximo 9 999 999 999.99, máximo 2 decimales; no redondear.
- Fechas de multa: infracción <= registro <= hoy; vencimiento >= registro. Pago: infracción <= pago <= hoy; anterior al registro es advertencia.
- Código inmutable; DNI de multa no cambia si tiene pagos; monto no menor a pagos vigentes.
- Pagos no exceden saldo; clave foránea compuesta (codigo_multa,dni_infractor). Comprobante único incluso anulado.
- Baja de multa solo sin ningún pago; pago se anula, no se elimina. Corrección de pago limitada a fecha, método y comprobante.
- Se bloquea multa al registrar/anular pagos o cambiar monto. Un lote completo se confirma en una transacción, con nueva validación contra DB.
- CSV estado_multa obligatorio: catálogo PENDIENTE/PARCIAL/PAGADA, solo informativo para conciliación, no genera pagos. Advertencia al diferir del calculado.
- Borradores duran 24 h; contenido temporal se purga al expirar/cancelar; metadatos de resultado permanecen.

Este archivo documenta el contrato de trabajo; el README explica la instalación y las decisiones finales.
