import { useState, type FormEvent } from 'react';
import { Search } from 'lucide-react';
import { Modal, Notice } from '../../components/ui';
import { api, errorMessage, fineFields, json, label, money, paymentFields, today } from '../../lib/api';
import type { Area, Catalogs, Data, Fine, Paginated, RecordItem } from '../../types';

export default function RecordForm({ area, record, catalogs, onClose, onSaved }: { area: Area; record?: RecordItem; catalogs: Catalogs; onClose: () => void; onSaved: (warnings?: string[]) => void }) {
  const isFine = area === 'multas';
  const fields = isFine ? fineFields : paymentFields;
  const [data, setData] = useState<Data>(() => Object.fromEntries(fields.map(field => [field, record ? String((record as unknown as Data)[field] ?? '') : ['fecha_registro', 'fecha_pago'].includes(field) ? today() : ''])));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [fine, setFine] = useState<Fine | null>(null);
  const [finding, setFinding] = useState(false);
  const [lookupError, setLookupError] = useState('');
  function set(key: string, value: string) { setData(d => ({ ...d, [key]: value })); if (key === 'codigo_multa') setFine(null); }
  async function findFine() {
    setFinding(true); setLookupError(''); setFine(null);
    try {
      const result = await api<Paginated<Fine>>(`/multas?q=${encodeURIComponent(data.codigo_multa)}&page_size=100`);
      const match = result.items.find(item => item.codigo_multa === data.codigo_multa.trim());
      if (!match) { setLookupError('No existe una multa vigente con ese código. Regístrala o impórtala antes de agregar el pago.'); return; }
      setFine(match); setData(d => ({ ...d, codigo_multa: match.codigo_multa, dni_infractor: match.dni_infractor }));
    } catch (err) { setLookupError(errorMessage(err)); } finally { setFinding(false); }
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    const payload = record ? Object.fromEntries(Object.entries(data).filter(([key]) => isFine ? key !== 'codigo_multa' : ['fecha_pago', 'metodo_pago', 'numero_comprobante'].includes(key))) : data;
    try { const result = await api<{ advertencias?: string[] }>(`/${area}${record ? `/${record.id}` : ''}`, { method: record ? 'PATCH' : 'POST', body: json(payload) }); onSaved(result.advertencias); }
    catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  return <Modal title={`${record ? 'Editar' : 'Registrar'} ${isFine ? 'multa' : 'pago'}`} subtitle={isFine ? 'El estado de cobranza se calcula automáticamente con los pagos.' : 'El pago debe corresponder a una multa existente y no exceder su saldo.'} onClose={onClose} busy={busy} wide>
    <form onSubmit={submit}><div className="modal-body"><div className="form-grid">{fields.map(field => {
      const readOnly = Boolean(record && (isFine ? field === 'codigo_multa' : ['codigo_multa', 'dni_infractor', 'monto_pagado'].includes(field)));
      const options = field === 'tipo_infraccion' ? catalogs.tipos_infraccion : field === 'metodo_pago' ? catalogs.metodos_pago : null;
      const isDate = field.startsWith('fecha_');
      const isMoney = field === 'monto' || field === 'monto_pagado';
      return <label key={field} className={`field ${field === 'descripcion' ? 'span-2' : ''}`}><span>{label(field)}{field !== 'descripcion' && <b aria-hidden="true"> *</b>}</span>{options ? <select value={data[field]} onChange={e => set(field, e.target.value)} required disabled={readOnly}><option value="">Selecciona una opción</option>{options.map(option => <option key={option.codigo} value={option.codigo}>{option.nombre}</option>)}</select> : field === 'descripcion' ? <textarea rows={3} value={data[field]} onChange={e => set(field, e.target.value)} maxLength={2000} placeholder="Detalles adicionales de la infracción (opcional)"/> : <div className={field === 'codigo_multa' && !isFine && !record ? 'input-action' : undefined}><input value={data[field]} onChange={e => set(field, e.target.value)} required readOnly={readOnly} type={isDate ? 'date' : isMoney ? 'number' : 'text'} step={isMoney ? '0.01' : undefined} min={isMoney ? '0.01' : undefined} max={isDate && field !== 'fecha_vencimiento' ? today() : isMoney ? '9999999999.99' : undefined} inputMode={field === 'dni_infractor' ? 'numeric' : isMoney ? 'decimal' : undefined} pattern={field === 'codigo_multa' ? 'MUL-[0-9]{14}' : field === 'dni_infractor' ? '[0-9]{8}' : undefined} maxLength={field === 'dni_infractor' ? 8 : field === 'codigo_multa' ? 18 : 200} placeholder={field === 'codigo_multa' ? 'MUL-00000000000001' : field === 'dni_infractor' ? '12345678' : isMoney ? '0.00' : undefined}/>{field === 'codigo_multa' && !isFine && !record && <button className="icon-button" aria-label="Buscar multa por código" title="Buscar multa" type="button" disabled={finding || !data.codigo_multa} onClick={findFine}><Search size={18}/></button>}</div>}{field === 'codigo_multa' && !isFine && !record && <small>Busca el código para consultar el saldo y completar el DNI.</small>}</label>;
    })}</div>
      {lookupError && <Notice tone="warning">{lookupError}</Notice>}{fine && <div className="balance-preview"><span>Multa {fine.codigo_multa}<small>DNI {fine.dni_infractor} · {fine.estado_multa.toLowerCase()}</small></span><strong>Saldo: {money(fine.saldo)}</strong></div>}
      {record && !isFine && <Notice tone="info">Para cambiar la multa, el DNI o el monto, anula este pago y registra uno nuevo.</Notice>}
      {error && <Notice>{error}</Notice>}<p className="small-muted">* Campos obligatorios. La operación quedará asociada a tu usuario declarado.</p>
    </div><div className="modal-actions"><button className="button secondary" type="button" onClick={onClose} disabled={busy}>Cancelar</button><button className="button primary" disabled={busy}>{busy ? 'Guardando…' : record ? 'Guardar cambios' : `Registrar ${isFine ? 'multa' : 'pago'}`}</button></div></form>
  </Modal>;
}
