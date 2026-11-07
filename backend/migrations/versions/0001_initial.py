"""Esquema inicial y catálogos de demostración.

Revision ID: 0001_initial
Revises:
"""
from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Esquema inicial congelado; cambios posteriores requieren otra revisión.
    op.create_table('auditoria',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('entidad', sa.String(length=30), nullable=False),
    sa.Column('registro_id', sa.Uuid(), nullable=False),
    sa.Column('accion', sa.String(length=30), nullable=False),
    sa.Column('usuario', sa.String(length=80), nullable=False),
    sa.Column('detalle', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_auditoria_entidad', 'auditoria', ['entidad', 'registro_id'], unique=False)
    op.create_table('importaciones',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('area', sa.String(length=16), nullable=False),
    sa.Column('nombre_archivo', sa.String(length=255), nullable=False),
    sa.Column('estado', sa.String(length=16), nullable=False),
    sa.Column('creado_por', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('configuracion', sa.JSON(), nullable=False),
    sa.Column('mensajes', sa.JSON(), nullable=False),
    sa.Column('vacias', sa.Integer(), nullable=False),
    sa.Column('total_original', sa.Integer(), nullable=False),
    sa.Column('resumen_final', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_importaciones_estado'), 'importaciones', ['estado'], unique=False)
    op.create_table('metodos_pago',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('codigo', sa.String(length=60), nullable=False),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo')
    )
    op.create_table('tipos_infraccion',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('codigo', sa.String(length=60), nullable=False),
    sa.Column('nombre', sa.String(length=120), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo')
    )
    op.create_table('filas_importacion',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('importacion_id', sa.Uuid(), nullable=False),
    sa.Column('numero_fila', sa.Integer(), nullable=False),
    sa.Column('datos_originales', sa.JSON(), nullable=False),
    sa.Column('datos', sa.JSON(), nullable=False),
    sa.Column('errores', sa.JSON(), nullable=False),
    sa.Column('advertencias', sa.JSON(), nullable=False),
    sa.Column('excluida', sa.Boolean(), nullable=False),
    sa.Column('resultado', sa.String(length=16), nullable=False),
    sa.Column('error_estructura', sa.Text(), nullable=True),
    sa.Column('registro_id', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['importacion_id'], ['importaciones.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('importacion_id', 'numero_fila', name='uq_importacion_numero_fila')
    )
    op.create_index('ix_importacion_resultado', 'filas_importacion', ['importacion_id', 'resultado'], unique=False)
    op.create_table('multas',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('codigo_multa', sa.String(length=18), nullable=False),
    sa.Column('dni_infractor', sa.String(length=8), nullable=False),
    sa.Column('tipo_infraccion', sa.String(length=60), nullable=False),
    sa.Column('descripcion', sa.Text(), nullable=False),
    sa.Column('fecha_infraccion', sa.Date(), nullable=False),
    sa.Column('lugar_infraccion', sa.String(length=255), nullable=False),
    sa.Column('monto', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('fecha_vencimiento', sa.Date(), nullable=False),
    sa.Column('fecha_registro', sa.Date(), nullable=False),
    sa.Column('creado_por', sa.String(length=80), nullable=False),
    sa.Column('actualizado_por', sa.String(length=80), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('eliminada_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motivo_eliminacion', sa.Text(), nullable=True),
    sa.CheckConstraint("codigo_multa ~ '^MUL-[0-9]{14}$'", name='ck_multa_codigo'),
    sa.CheckConstraint("dni_infractor ~ '^[0-9]{8}$'", name='ck_multa_dni'),
    sa.CheckConstraint('fecha_infraccion <= fecha_registro', name='ck_multa_fechas_registro'),
    sa.CheckConstraint('fecha_vencimiento >= fecha_registro', name='ck_multa_fechas_vencimiento'),
    sa.CheckConstraint('length(trim(lugar_infraccion)) > 0', name='ck_multa_lugar'),
    sa.CheckConstraint('monto > 0 AND monto <= 9999999999.99', name='ck_multa_monto'),
    sa.ForeignKeyConstraint(['tipo_infraccion'], ['tipos_infraccion.codigo'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo_multa'),
    sa.UniqueConstraint('codigo_multa', 'dni_infractor', name='uq_multa_codigo_dni')
    )
    op.create_index(op.f('ix_multas_dni_infractor'), 'multas', ['dni_infractor'], unique=False)
    op.create_index(op.f('ix_multas_fecha_infraccion'), 'multas', ['fecha_infraccion'], unique=False)
    op.create_index(op.f('ix_multas_tipo_infraccion'), 'multas', ['tipo_infraccion'], unique=False)
    op.create_index('ix_multas_vencimiento', 'multas', ['fecha_vencimiento'], unique=False)
    op.create_table('pagos',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('codigo_multa', sa.String(length=18), nullable=False),
    sa.Column('dni_infractor', sa.String(length=8), nullable=False),
    sa.Column('fecha_pago', sa.Date(), nullable=False),
    sa.Column('monto_pagado', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('metodo_pago', sa.String(length=60), nullable=False),
    sa.Column('numero_comprobante', sa.String(length=120), nullable=False),
    sa.Column('creado_por', sa.String(length=80), nullable=False),
    sa.Column('actualizado_por', sa.String(length=80), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('anulado_en', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motivo_anulacion', sa.Text(), nullable=True),
    sa.CheckConstraint('length(trim(numero_comprobante)) > 0', name='ck_pago_comprobante'),
    sa.CheckConstraint('monto_pagado > 0 AND monto_pagado <= 9999999999.99', name='ck_pago_monto'),
    sa.ForeignKeyConstraint(['codigo_multa', 'dni_infractor'], ['multas.codigo_multa', 'multas.dni_infractor'], name='fk_pago_multa_dni', onupdate='RESTRICT', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['metodo_pago'], ['metodos_pago.codigo'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('numero_comprobante')
    )
    op.create_index(op.f('ix_pagos_dni_infractor'), 'pagos', ['dni_infractor'], unique=False)
    op.create_index(op.f('ix_pagos_fecha_pago'), 'pagos', ['fecha_pago'], unique=False)
    op.create_index('ix_pagos_multa_dni', 'pagos', ['codigo_multa', 'dni_infractor'], unique=False)

    tipos = sa.table("tipos_infraccion", sa.column("id", sa.Uuid()), sa.column("codigo", sa.String()), sa.column("nombre", sa.String()))
    metodos = sa.table("metodos_pago", sa.column("id", sa.Uuid()), sa.column("codigo", sa.String()), sa.column("nombre", sa.String()))
    op.bulk_insert(tipos, [
        {"id": UUID("10000000-0000-4000-8000-000000000001"), "codigo": "EXCESO_VELOCIDAD", "nombre": "Exceso de velocidad"},
        {"id": UUID("10000000-0000-4000-8000-000000000002"), "codigo": "ESTACIONAMIENTO_INDEBIDO", "nombre": "Estacionamiento indebido"},
        {"id": UUID("10000000-0000-4000-8000-000000000003"), "codigo": "SEMAFORO_ROJO", "nombre": "Cruzar semáforo en rojo"},
        {"id": UUID("10000000-0000-4000-8000-000000000004"), "codigo": "DOCUMENTACION", "nombre": "Documentación incompleta"},
    ])
    op.bulk_insert(metodos, [
        {"id": UUID("20000000-0000-4000-8000-000000000001"), "codigo": "EFECTIVO", "nombre": "Efectivo"},
        {"id": UUID("20000000-0000-4000-8000-000000000002"), "codigo": "TRANSFERENCIA", "nombre": "Transferencia bancaria"},
        {"id": UUID("20000000-0000-4000-8000-000000000003"), "codigo": "TARJETA", "nombre": "Tarjeta"},
        {"id": UUID("20000000-0000-4000-8000-000000000004"), "codigo": "YAPE", "nombre": "Yape"},
        {"id": UUID("20000000-0000-4000-8000-000000000005"), "codigo": "PLIN", "nombre": "Plin"},
    ])


def downgrade():
    op.drop_table('pagos')
    op.drop_table('multas')
    op.drop_table('filas_importacion')
    op.drop_table('tipos_infraccion')
    op.drop_table('metodos_pago')
    op.drop_table('importaciones')
    op.drop_table('auditoria')
