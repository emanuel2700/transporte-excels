import { useEffect, useState, type FormEvent } from 'react';
import { Eye, Pencil, Plus, Search, Trash2, UploadCloud, Filter, X } from 'lucide-react';
import { Badge, Empty, Modal, Notice, Pagination, Spinner } from '../../components/ui';
import { api, date, errorMessage, fineFields, json, label, money, paymentFields } from '../../lib/api';
import type { Area, Catalogs, Data, Fine, Page, Paginated, Payment, RecordItem } from '../../types';
import RecordForm from './RecordForm';
import HistoryDetails from './HistoryDetails';

export default function Records({ area, catalogs, navigate }: { area: Area; catalogs: Catalogs; navigate: (page: Page) => void }) {
  const isFine = area === 'multas';
  const [data, setData] = useState<Paginated<RecordItem>>({ items: [], total: 0, page: 1, page_size: 20 });
  const [filters, setFilters] = useState({ q: '', estado: '', tipo_infraccion: '', metodo_pago: '', desde: '', hasta: '', incluir_anulados: 'false' });
  const [query, setQuery] = useState(filters);
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]);
  const [form, setForm] = useState<RecordItem | 'new' | null>(null);
  const [detail, setDetail] = useState<RecordItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deleting, setDeleting] = useState<RecordItem | null>(null);
  const [reason, setReason] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true; setLoading(true); setError('');
    const params = new URLSearchParams({ ...Object.fromEntries(Object.entries(query).filter(([, value]) => value !== '')), page: String(page), page_size: '20' });
    api<Paginated<RecordItem>>(`/${area}?${params}`).then(result => { if (active) setData(result); }).catch(err => { if (active) setError(errorMessage(err)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [area, query, page, refresh]);
  async function openDetail(item: RecordItem) {
    setDetailLoading(true); setDetail(item); setError('');
    try { setDetail(await api<RecordItem>(`/${area}/${item.id}`)); } catch (err) { setError(errorMessage(err)); setDetail(null); } finally { setDetailLoading(false); }
  }
  function saved(messages: string[] = []) { setForm(null); setSuccess('El registro se guardó correctamente.'); setWarnings(messages); setRefresh(n => n + 1); }
  function askDelete(item: RecordItem) { setDeleting(item); setReason(''); setDeleteError(''); }
  async function remove(event: FormEvent) {
    event.preventDefault(); if (!deleting) return; setBusy(true); setDeleteError('');
    try { await api(`/${area}/${deleting.id}`, { method: 'DELETE', body: json({ motivo: reason }) }); setDeleting(null); setDetail(null); setSuccess(isFine ? 'La multa fue dada de baja. Se conserva su historial.' : 'El pago fue anulado y el saldo se recalculó.'); setRefresh(n => n + 1); }
    catch (err) { setDeleteError(errorMessage(err)); } finally { setBusy(false); }
  }
  function filter(event: FormEvent) { event.preventDefault(); setPage(1); setQuery(filters); }
  const activeFilters = query.q || query.estado || query.tipo_infraccion || query.metodo_pago || query.desde || query.hasta || query.incluir_anulados === 'true';
  function resetFilters() { const empty = { q: '', estado: '', tipo_infraccion: '', metodo_pago: '', desde: '', hasta: '', incluir_anulados: 'false' }; setFilters(empty); setQuery(empty); setPage(1); }
  return <>
    <div className="page-heading"><div><span className="eyebrow">{isFine ? 'TRÁNSITO Y FISCALIZACIÓN' : 'COBRANZAS'}</span><h1>{isFine ? 'Gestión de multas' : 'Gestión de pagos'}</h1><p>{isFine ? 'Consulta infracciones, controla vencimientos y revisa saldos.' : 'Registra abonos y consulta el historial de tus comprobantes.'}</p></div><div className="heading-actions"><button className="button secondary" onClick={() => navigate('importaciones')}><UploadCloud size={17}/>Importar CSV</button><button className="button primary" onClick={() => setForm('new')}><Plus size={18}/>{isFine ? 'Nueva multa' : 'Nuevo pago'}</button></div></div>
    {success && <Notice tone="success">{success}<button className="inline-close" aria-label="Cerrar mensaje" onClick={() => setSuccess('')}><X size={15}/></button></Notice>}
    {warnings.map((message, index) => <Notice key={index} tone="warning">{message}</Notice>)}
    {error && <Notice>{error} <button className="text-button" onClick={() => setRefresh(n => n + 1)}>Reintentar</button></Notice>}
    <section className="panel"><div className="panel-title"><h2>{isFine ? 'Registro de multas' : 'Registro de pagos'}</h2><span className="count-pill">{data.total} registros</span></div>
      <form className="filters" onSubmit={filter}><label className="field search-field"><span>Buscar</span><div className="input-icon"><Search size={17}/><input value={filters.q} onChange={e => setFilters(f => ({ ...f, q: e.target.value }))} placeholder={isFine ? 'Código de multa o DNI' : 'Comprobante, multa o DNI'}/></div></label>
        {isFine ? <><label className="field"><span>Estado de cobranza</span><select value={filters.estado} onChange={e => setFilters(f => ({ ...f, estado: e.target.value }))}><option value="">Todos los estados</option><option>PENDIENTE</option><option>PARCIAL</option><option>PAGADA</option></select></label><label className="field"><span>Tipo de infracción</span><select value={filters.tipo_infraccion} onChange={e => setFilters(f => ({ ...f, tipo_infraccion: e.target.value }))}><option value="">Todas las infracciones</option>{catalogs.tipos_infraccion.map(item => <option value={item.codigo} key={item.codigo}>{item.nombre}</option>)}</select></label></> : <label className="field"><span>Método de pago</span><select value={filters.metodo_pago} onChange={e => setFilters(f => ({ ...f, metodo_pago: e.target.value }))}><option value="">Todos los métodos</option>{catalogs.metodos_pago.map(item => <option value={item.codigo} key={item.codigo}>{item.nombre}</option>)}</select></label>}
        <label className="field"><span>Desde ({isFine ? 'infracción' : 'pago'})</span><input type="date" value={filters.desde} onChange={e => setFilters(f => ({ ...f, desde: e.target.value }))}/></label><label className="field"><span>Hasta</span><input type="date" min={filters.desde || undefined} value={filters.hasta} onChange={e => setFilters(f => ({ ...f, hasta: e.target.value }))}/></label>
        {!isFine && <label className="checkbox-field"><input type="checkbox" checked={filters.incluir_anulados === 'true'} onChange={e => setFilters(f => ({ ...f, incluir_anulados: String(e.target.checked) }))}/>Incluir anulados</label>}
        <button className="button secondary" type="submit"><Filter size={16}/>Filtrar</button>{activeFilters && <button className="text-button" type="button" onClick={resetFilters}>Limpiar</button>}
      </form>
      {loading ? <Spinner/> : !data.items.length ? <Empty title={activeFilters ? 'No se encontraron registros' : isFine ? 'Aún no hay multas registradas' : 'Aún no hay pagos registrados'} description={activeFilters ? 'Prueba con otros filtros o limpia la búsqueda.' : 'Crea el primer registro o importa tus archivos CSV para comenzar.'} action={!activeFilters && <button className="button primary" onClick={() => setForm('new')}><Plus size={17}/>{isFine ? 'Registrar multa' : 'Registrar pago'}</button>}/> : <div className="table-scroll"><table><thead><tr>{isFine ? <><th>Multa / infractor</th><th>Infracción</th><th>Monto</th><th>Saldo</th><th>Estado</th><th>Vencimiento</th></> : <><th>Comprobante / multa</th><th>DNI</th><th>Fecha de pago</th><th>Monto pagado</th><th>Método</th><th>Estado</th></>}<th><span className="sr-only">Acciones</span></th></tr></thead><tbody>{data.items.map(item => {
        const fine = item as Fine; const payment = item as Payment; const inactive = isFine ? Boolean(fine.eliminada_en) : Boolean(payment.anulado_en);
        return <tr key={item.id}>{isFine ? <><td><button className="record-link" onClick={() => openDetail(item)}>{item.codigo_multa}</button><small>DNI {item.dni_infractor}</small></td><td>{catalogs.tipos_infraccion.find(c => c.codigo === fine.tipo_infraccion)?.nombre || fine.tipo_infraccion}<small>{date(fine.fecha_infraccion)}</small></td><td className="amount">{money(fine.monto)}</td><td className="amount">{money(fine.saldo)}</td><td><Badge value={fine.estado_multa}/>{fine.vencida && <small className="text-red">Vencida</small>}</td><td>{date(fine.fecha_vencimiento)}</td></> : <><td><button className="record-link" onClick={() => openDetail(item)}>{payment.numero_comprobante}</button><small>{payment.codigo_multa}</small></td><td>{payment.dni_infractor}</td><td>{date(payment.fecha_pago)}</td><td className="amount">{money(payment.monto_pagado)}</td><td>{catalogs.metodos_pago.find(c => c.codigo === payment.metodo_pago)?.nombre || payment.metodo_pago}</td><td><Badge value={inactive ? 'ANULADO' : 'REGISTRADO'}/></td></>}
          <td><div className="row-actions"><button className="icon-button" title="Ver detalle" aria-label={`Ver detalle de ${isFine ? item.codigo_multa : payment.numero_comprobante}`} onClick={() => openDetail(item)}><Eye size={17}/></button>{!inactive && <><button className="icon-button" title="Editar" aria-label={`Editar ${isFine ? item.codigo_multa : payment.numero_comprobante}`} onClick={() => setForm(item)}><Pencil size={16}/></button><button className="icon-button danger-text" title={isFine ? 'Dar de baja' : 'Anular pago'} aria-label={`${isFine ? 'Dar de baja' : 'Anular'} ${isFine ? item.codigo_multa : payment.numero_comprobante}`} onClick={() => askDelete(item)}><Trash2 size={16}/></button></>}</div></td>
        </tr>;
      })}</tbody></table></div>}
      <Pagination page={page} total={data.total} pageSize={20} onChange={setPage} disabled={loading}/>
    </section>
    <p className="page-footnote">{isFine ? 'Pendiente, parcial y pagada se calculan según los pagos vigentes. La baja de una multa requiere que no tenga pagos asociados.' : 'Los pagos anulados se conservan en el historial y no se incluyen en el saldo pagado.'}</p>
    {form && <RecordForm area={area} record={form === 'new' ? undefined : form} catalogs={catalogs} onClose={() => setForm(null)} onSaved={saved}/>}
    {detail && <Modal title={isFine ? 'Detalle de multa' : 'Detalle de pago'} subtitle={isFine ? detail.codigo_multa : (detail as Payment).numero_comprobante} onClose={() => setDetail(null)} wide>{detailLoading ? <Spinner/> : <div className="modal-body">
      {isFine && <div className="detail-summary"><div><span>Monto de multa</span><strong>{money((detail as Fine).monto)}</strong></div><div><span>Total pagado</span><strong>{money((detail as Fine).total_pagado)}</strong></div><div><span>Saldo pendiente</span><strong>{money((detail as Fine).saldo)}</strong></div><Badge value={(detail as Fine).estado_multa}/></div>}
      <dl className="detail-grid">{(isFine ? fineFields : paymentFields).map(field => <div key={field}><dt>{label(field)}</dt><dd>{field.startsWith('fecha_') ? date((detail as unknown as Data)[field]) : ['monto', 'monto_pagado'].includes(field) ? money((detail as unknown as Data)[field]) : (detail as unknown as Data)[field] || '—'}</dd></div>)}<div><dt>Creado por</dt><dd>{detail.creado_por}</dd></div><div><dt>Última actualización</dt><dd>{detail.actualizado_por} · {date(detail.updated_at)}</dd></div></dl>
      {!isFine && (detail as Payment).anulado_en && <Notice tone="warning">Pago anulado: {(detail as Payment).motivo_anulacion}</Notice>}
      {isFine && <section className="detail-section"><h3>Pagos asociados</h3>{(detail as Fine).pagos?.length ? <div className="table-scroll"><table><thead><tr><th>Comprobante</th><th>Fecha</th><th>Monto</th><th>Estado</th></tr></thead><tbody>{(detail as Fine).pagos!.map(payment => <tr key={payment.id}><td>{payment.numero_comprobante}</td><td>{date(payment.fecha_pago)}</td><td>{money(payment.monto_pagado)}</td><td><Badge value={payment.anulado_en ? 'ANULADO' : 'REGISTRADO'}/></td></tr>)}</tbody></table></div> : <p className="small-muted">Esta multa aún no tiene pagos registrados.</p>}</section>}
      <section className="detail-section"><h3>Historial de operaciones</h3>{detail.historial?.length ? <ol className="timeline">{detail.historial.map(event => <li key={event.id}><span className="timeline-dot"/><div><strong>{event.accion.replaceAll('_', ' ')}</strong><p>{event.usuario} · {date(event.created_at)}</p>{event.detalle != null && <HistoryDetails detail={event.detalle} catalogs={catalogs}/>}</div></li>)}</ol> : <p className="small-muted">Sin eventos adicionales.</p>}</section>
    </div>}<div className="modal-actions"><button className="button secondary" onClick={() => setDetail(null)}>Cerrar</button></div></Modal>}
    {deleting && <Modal title={isFine ? 'Dar de baja la multa' : 'Anular el pago'} subtitle={isFine ? deleting.codigo_multa : (deleting as Payment).numero_comprobante} onClose={() => setDeleting(null)} busy={busy}><form onSubmit={remove}><div className="modal-body"><Notice tone="warning">{isFine ? 'La multa dejará de aparecer en los registros vigentes. Solo se permite si no tiene pagos asociados.' : 'El importe dejará de contar como pagado y se recalculará el saldo. El comprobante permanecerá reservado.'} El historial se conserva.</Notice><label className="field"><span>Motivo *</span><textarea required minLength={3} maxLength={1000} rows={3} value={reason} onChange={e => setReason(e.target.value)} placeholder="Explica por qué se realiza esta operación"/></label>{deleteError && <Notice>{deleteError}</Notice>}</div><div className="modal-actions"><button className="button secondary" type="button" disabled={busy} onClick={() => setDeleting(null)}>Cancelar</button><button className="button danger" disabled={busy || reason.trim().length < 3}>{busy ? 'Procesando…' : isFine ? 'Confirmar baja' : 'Confirmar anulación'}</button></div></form></Modal>}
  </>;
}
