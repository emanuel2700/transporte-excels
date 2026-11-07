# Reglas de negocio de la prueba de concepto

## Multas

- Código obligatorio, único e inmutable: `MUL-` + 14 dígitos ASCII.
- DNI obligatorio: 8 dígitos ASCII, almacenados como texto.
- Tipo de infracción del catálogo de demostración; lugar, monto y fechas obligatorios. Descripción opcional.
- Infracción <= registro <= fecha actual de Lima. Vencimiento >= registro.
- Monto mayor que cero, finito, hasta 9 999 999 999.99, sin más de 2 decimales.
- Estado calculado: sin pagos vigentes `PENDIENTE`, pagos menores al monto `PARCIAL`, saldo cero `PAGADA`.
- Vencida cuando tiene saldo y vencimiento anterior al día actual.
- DNI no cambia si existe cualquier pago, incluso anulado. No se reduce el monto por debajo de pagos vigentes.
- Baja lógica solo sin pagos, con motivo. El código de una multa dada de baja no se reutiliza.

## Pagos

- Todos los campos solicitados son obligatorios.
- La multa debe existir, estar activa y corresponder al DNI. La clave foránea compuesta refuerza la asociación en PostgreSQL.
- Fecha >= infracción y <= hoy; anterior al registro produce advertencia.
- Monto positivo, hasta 2 decimales, no superior al saldo disponible. Varias filas del mismo lote se evalúan conjuntamente.
- Comprobante único global; no se reutiliza después de una anulación.
- Solo se editan fecha, método y comprobante. Para cambiar monto o multa se anula con motivo y se crea un registro nuevo.
- Anulación conserva el pago y el historial; deja de sumar al total pagado.

## Importaciones

- Campos con formato ambiguo no se convierten silenciosamente. Se seleccionan codificación, separador, fechas y decimal para todo el archivo.
- Una columna obligatoria faltante bloquea la carga. Columnas adicionales se advierten e ignoran. Encabezados inesperados admiten mapeo explícito.
- Filas vacías se contabilizan y omiten. Las filas con errores pueden corregirse o excluirse.
- DNI, código, fechas, montos o catálogos inválidos bloquean la fila. La ausencia de descripción es advertencia.
- Duplicado exacto dentro del archivo: conservar una copia; omitir las demás con advertencia. Misma clave con datos distintos: error.
- Duplicado exacto en base: excluir como ya registrado. Misma clave existente con cambios: error; no hay upsert.
- Pagos con misma multa, fecha y monto, pero distinto comprobante: advertencia de posible duplicado.
- Estados CSV `PENDIENTE`, `PARCIAL` y `PAGADA` son información declarada; la diferencia frente al cálculo produce advertencia para conciliación.
- Confirmar inserta las filas elegibles del resumen aprobado. Una selección modificada por conflictos detectados al confirmar debe volver a revisarse.
- No hay commits por fila ni importaciones ocultamente parciales. Fallo de guardado revierte el intento completo.
- Cualquier sesión de demostración puede revisar, editar, validar, confirmar o cancelar un borrador. No hay permisos por área ni por propietario del lote.
- El lote conserva en `creado_por` a quien cargó el archivo. Las multas o los pagos importados y su auditoría registran a quien confirma el lote, aunque sea otro usuario declarado.

## Supuestos

Moneda única PEN; sin intereses, descuentos ni devoluciones. Un comprobante identifica un único pago de una multa. Catálogos de demostración, pendientes de validación con la empresa. El usuario de creación en una importación es quien confirma el lote, no un operador histórico inferido del CSV.
