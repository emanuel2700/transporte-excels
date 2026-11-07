export type Area = 'multas' | 'pagos';
export type Page = 'inicio' | Area | 'importaciones';
export type Data = Record<string, string>;
export interface CatalogItem { codigo: string; nombre: string }
export interface Catalogs { tipos_infraccion: CatalogItem[]; metodos_pago: CatalogItem[] }
export interface History { id: string; accion: string; usuario: string; created_at: string; detalle: unknown }
export interface Fine {
  id: string; codigo_multa: string; dni_infractor: string; tipo_infraccion: string;
  descripcion: string; fecha_infraccion: string; lugar_infraccion: string; monto: string;
  fecha_vencimiento: string; fecha_registro: string; estado_multa: string;
  total_pagado: string; saldo: string; vencida: boolean; creado_por: string;
  actualizado_por: string; created_at: string; updated_at: string;
  eliminada_en: string | null; pagos?: Payment[]; historial?: History[];
}
export interface Payment {
  id: string; codigo_multa: string; dni_infractor: string; fecha_pago: string;
  monto_pagado: string; metodo_pago: string; numero_comprobante: string;
  anulado_en: string | null; motivo_anulacion: string | null; creado_por: string;
  actualizado_por: string; created_at: string; updated_at: string; historial?: History[];
}
export type RecordItem = Fine | Payment;
export interface Paginated<T> { items: T[]; total: number; page: number; page_size: number }
export interface DashboardData {
  multas: number; total_multas: string; total_pagado: string; saldo_pendiente: string;
  pagos: number; multas_vencidas: number;
}
export interface ImportRow {
  id: string; numero_fila: number; datos: Data; errores: string[]; advertencias: string[];
  excluida: boolean; resultado: string; registro_id: string | null;
}
export interface ImportSummary {
  listas: number; advertencias: number; errores: number; excluidas: number; vacias: number; importadas: number;
}
export interface ImportBatch {
  id: string; area: Area; nombre_archivo: string; estado: string; creado_por: string;
  created_at: string; expires_at: string; resumen: ImportSummary; filas: ImportRow[];
  total_filas: number; page: number; page_size: number; mensajes: string[];
}
