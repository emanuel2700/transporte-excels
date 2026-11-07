export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isForm = options.body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options, credentials: 'same-origin',
      headers: { ...(!isForm && options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
    });
  } catch { throw new ApiError('No se pudo conectar con el servidor. Comprueba la conexión y vuelve a intentarlo.', 0); }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login' && path !== '/auth/me') window.dispatchEvent(new Event('session-expired'));
    const detail = data?.detail;
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.map((item: { loc?: string[]; msg?: string }) => `${item.loc?.slice(1).join('.') || 'Dato'}: ${item.msg}`).join(' · ')
      : 'No se pudo completar la operación. Inténtalo de nuevo.';
    throw new ApiError(message, response.status);
  }
  return data as T;
}

export const json = (value: unknown) => JSON.stringify(value);
export const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Ocurrió un error inesperado.';
export const money = (value: string | number | undefined) => new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' }).format(Number(value || 0));
export const date = (value?: string | null) => value ? new Intl.DateTimeFormat('es-PE', { dateStyle: 'medium', timeZone: 'America/Lima' }).format(new Date(value.length === 10 ? `${value}T12:00:00-05:00` : value)) : '—';
export const today = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Lima', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
export const label = (key: string) => ({
  codigo_multa: 'Código de multa', dni_infractor: 'DNI del infractor', tipo_infraccion: 'Tipo de infracción',
  descripcion: 'Descripción', fecha_infraccion: 'Fecha de infracción', lugar_infraccion: 'Lugar de infracción',
  monto: 'Monto de la multa', estado_multa: 'Estado declarado', fecha_vencimiento: 'Fecha de vencimiento',
  fecha_registro: 'Fecha de registro', fecha_pago: 'Fecha de pago', monto_pagado: 'Monto pagado',
  metodo_pago: 'Método de pago', numero_comprobante: 'Número de comprobante',
}[key] || key);
export const fineFields = ['codigo_multa', 'dni_infractor', 'tipo_infraccion', 'descripcion', 'fecha_infraccion', 'lugar_infraccion', 'monto', 'fecha_vencimiento', 'fecha_registro'];
export const paymentFields = ['codigo_multa', 'fecha_pago', 'monto_pagado', 'metodo_pago', 'numero_comprobante', 'dni_infractor'];
