import { date, fineFields, label, money, paymentFields } from '../../lib/api';
import type { Catalogs } from '../../types';

const businessFields = [...new Set([...fineFields, ...paymentFields])];
const asObject = (value: unknown): Record<string, unknown> | null => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;

export default function HistoryDetails({ detail, catalogs }: { detail: unknown; catalogs: Catalogs }) {
  const data = asObject(detail);
  if (!data) return typeof detail === 'string' && detail.trim() ? <p className="history-reason">{detail}</p> : null;

  const before = asObject(data.antes);
  const after = asObject(data.despues);
  const fields = after ? businessFields.filter(field => field in after && (!before || String(before[field] ?? '') !== String(after[field] ?? ''))) : [];
  const reason = typeof data.motivo === 'string' ? data.motivo : '';

  function format(field: string, value: unknown): string {
    if (value === null || value === undefined || value === '') return 'Sin dato';
    if (typeof value !== 'string' && typeof value !== 'number') return 'Sin dato';
    const text = String(value);
    if (field === 'monto' || field === 'monto_pagado') return money(text);
    if (field.startsWith('fecha_')) return date(text);
    const choices = field === 'tipo_infraccion' ? catalogs.tipos_infraccion : field === 'metodo_pago' ? catalogs.metodos_pago : [];
    return choices.find(item => item.codigo === text)?.nombre || text;
  }

  if (!reason && !fields.length) return <p className="small-muted">No se modificaron datos del registro.</p>;
  return <details><summary>Ver cambios</summary><div className="history-changes">
    {reason && <p className="history-reason"><strong>Motivo:</strong> {reason}</p>}
    {fields.length > 0 && <dl>{fields.map(field => <div key={field}><dt>{label(field)}</dt><dd>{before && <><span className="history-before">{format(field, before[field])}</span><span className="history-arrow" aria-label="cambió a"> → </span></>}<span>{format(field, after![field])}</span></dd></div>)}</dl>}
  </div></details>;
}
