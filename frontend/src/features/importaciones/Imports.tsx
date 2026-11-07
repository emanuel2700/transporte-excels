import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Download, Eye, FileSpreadsheet, History, Pencil, Plus, RefreshCw, Trash2, UploadCloud, X } from 'lucide-react';
import { Badge, Empty, Modal, Notice, Pagination, Spinner } from '../../components/ui';
import { api, date, errorMessage, fineFields, json, label, paymentFields } from '../../lib/api';
import type { Area, Catalogs, Data, ImportBatch, ImportRow, Paginated } from '../../types';

export default function Imports({ catalogs }: { catalogs: Catalogs }) {
  const [tab, setTab] = useState<'new' | 'history'>('new');
  const [area, setArea] = useState<Area>('multas');
  const [file, setFile] = useState<File | null>(null);
  const [encoding, setEncoding] = useState('utf-8-sig');
  const [delimiter, setDelimiter] = useState(',');
  const [dateFormat, setDateFormat] = useState('iso');
  const [decimalSeparator, setDecimalSeparator] = useState('.');
  const [mapping, setMapping] = useState<{ from: string; to: string }[]>([]);
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [history, setHistory] = useState<Paginated<ImportBatch>>({ items: [], total: 0, page: 1, page_size: 20 });
  const [historyPage, setHistoryPage] = useState(1);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editing, setEditing] = useState<ImportRow | null>(null);
  const [editData, setEditData] = useState<Data>({});
  const [editError, setEditError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [accept, setAccept] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const fileInput = useRef<HTMLInputElement>(null);
  const expectedFields = area === 'multas' ? [...fineFields.slice(0, 7), 'estado_multa', ...fineFields.slice(7)] : paymentFields;
  const editable = batch?.estado === 'BORRADOR';
  const summary = batch?.resumen;
  const eligible = (summary?.listas || 0) + (summary?.advertencias || 0);

  useEffect(() => {
    if (tab !== 'history' || batch) return;
    let active = true; setLoadingHistory(true); setError('');
    api<Paginated<ImportBatch>>(`/importaciones?page=${historyPage}&page_size=20`).then(result => { if (active) setHistory(result); }).catch(err => { if (active) setError(errorMessage(err)); }).finally(() => { if (active) setLoadingHistory(false); });
    return () => { active = false; };
  }, [tab, historyPage, batch, refresh]);

  function selectFile(next: File | null) {
    setError('');
    if (next && next.size > 10 * 1024 * 1024) { setError('El archivo supera el límite de 10 MB. Divide los registros en archivos más pequeños.'); return; }
    setFile(next);
  }
  async function upload(event: FormEvent) {
    event.preventDefault(); if (!file) return; setBusy(true); setError(''); setSuccess('');
    const form = new FormData();
    form.append('file', file); form.append('area', area); form.append('encoding', encoding); form.append('delimiter', delimiter); form.append('date_format', dateFormat); form.append('decimal_separator', decimalSeparator);
    const configured = mapping.filter(item => item.from.trim() && item.to);
    if (configured.length) form.append('column_mapping', json(Object.fromEntries(configured.map(item => [item.from.trim(), item.to]))));
    try { setBatch(await api<ImportBatch>('/importaciones', { method: 'POST', body: form })); }
    catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  async function open(id: string, page = 1) {
    setBusy(true); setError('');
    try { setBatch(await api<ImportBatch>(`/importaciones/${id}?page=${page}&page_size=50`)); }
    catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  async function refreshBatch() { if (batch) setBatch(await api<ImportBatch>(`/importaciones/${batch.id}?page=${batch.page || 1}&page_size=50`)); }
  async function operation(path: string, message: string, body?: unknown) {
    if (!batch) return; setBusy(true); setError(''); setSuccess('');
    try { const result = await api<ImportBatch>(`/importaciones/${batch.id}/${path}`, { method: 'POST', ...(body ? { body: json(body) } : {}) }); setBatch(result); setSuccess(message); }
    catch (err) {
      setError(errorMessage(err));
      try {
        const current = await api<ImportBatch>(`/importaciones/${batch.id}`); setBatch(current);
        if (path === 'confirmar' && current.estado === 'CONFIRMADA') { setError(''); setSuccess('Se verificó que la importación fue confirmada. No se duplicaron los registros.'); }
      } catch { setError(`${errorMessage(err)} No fue posible verificar el estado del lote. Usa «Actualizar estado» antes de reintentar.`); }
    } finally { setBusy(false); setConfirming(false); setCanceling(false); }
  }
  function startEdit(row: ImportRow) { setEditing(row); setEditData({ ...row.datos }); setEditError(''); }
  async function saveRow(event: FormEvent) {
    event.preventDefault(); if (!batch || !editing) return; setBusy(true); setEditError('');
    try { await api(`/importaciones/${batch.id}/filas/${editing.id}`, { method: 'PATCH', body: json({ datos: editData, excluida: false }) }); await refreshBatch(); setEditing(null); setSuccess('Fila actualizada. Revisa la validación antes de confirmar.'); }
    catch (err) { setEditError(errorMessage(err)); } finally { setBusy(false); }
  }
  async function toggleRow(row: ImportRow) {
    if (!batch) return; setBusy(true); setError('');
    try { await api(`/importaciones/${batch.id}/filas/${row.id}`, { method: 'PATCH', body: json({ datos: row.datos, excluida: !row.excluida }) }); await refreshBatch(); }
    catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  function back() { setBatch(null); setSuccess(''); setError(''); setRefresh(n => n + 1); }
  async function download() {
    if (!batch) return; setError('');
    try {
      const response = await fetch(`/api/importaciones/${batch.id}/reporte`, { credentials: 'same-origin' });
      if (!response.ok) throw new Error('No se pudo descargar el reporte. Actualiza el estado e inténtalo de nuevo.');
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = `resultado-${batch.id}.csv`; document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { setError(errorMessage(err)); }
  }

  return <>
    <div className="page-heading"><div><span className="eyebrow">MIGRACIÓN DE REGISTROS</span><h1>Importaciones CSV</h1><p>Revisa y corrige tus datos antes de incorporarlos a la plataforma.</p></div>{batch && <button className="button secondary" onClick={back} disabled={busy}><ArrowLeft size={17}/>Volver</button>}</div>
    {error && <Notice>{error}</Notice>}{success && <Notice tone="success">{success}</Notice>}
    {!batch ? <>
      <div className="tabs" role="tablist" aria-label="Importaciones"><button role="tab" aria-selected={tab === 'new'} className={tab === 'new' ? 'active' : ''} onClick={() => setTab('new')}><UploadCloud size={18}/>Nueva importación</button><button role="tab" aria-selected={tab === 'history'} className={tab === 'history' ? 'active' : ''} onClick={() => setTab('history')}><History size={18}/>Historial y borradores</button></div>
      {tab === 'new' ? <form onSubmit={upload} className="import-layout">
        <section className="panel upload-panel"><div className="panel-title"><h2><span className="step-number">1</span>Selecciona el archivo</h2></div><div className="panel-body"><label className="field"><span>Área de los registros</span><select value={area} onChange={e => { setArea(e.target.value as Area); setMapping([]); }}><option value="multas">Tránsito y Fiscalización — Multas</option><option value="pagos">Cobranzas — Pagos</option></select></label>
          <div className={`dropzone ${file ? 'has-file' : ''}`} onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (e.dataTransfer.files.length > 1) setError('Selecciona un solo archivo CSV por importación.'); else selectFile(e.dataTransfer.files[0] || null); }}><span className="upload-icon">{file ? <FileSpreadsheet size={32}/> : <UploadCloud size={32}/>}</span><strong>{file ? file.name : 'Arrastra tu archivo CSV aquí'}</strong><p>{file ? `${(file.size / 1024).toFixed(1)} KB · Listo para revisar` : 'o selecciónalo desde tu equipo'}</p><button type="button" className="button secondary" onClick={() => fileInput.current?.click()}>{file ? 'Cambiar archivo' : 'Seleccionar archivo'}</button><input ref={fileInput} type="file" accept=".csv,text/csv,text/plain" className="sr-only" aria-label="Archivo CSV" onChange={e => selectFile(e.target.files?.[0] || null)}/><small>Hasta 10 MB y 20 000 filas por archivo</small></div>
          <div className="section-heading compact"><h3>Formato del archivo</h3></div><div className="form-grid"><label className="field"><span>Codificación</span><select value={encoding} onChange={e => setEncoding(e.target.value)}><option value="utf-8-sig">UTF-8 (con o sin BOM)</option><option value="cp1252">Windows-1252</option></select></label><label className="field"><span>Separador de columnas</span><select value={delimiter} onChange={e => setDelimiter(e.target.value)}><option value=",">Coma (,)</option><option value=";">Punto y coma (;)</option><option value="tab">Tabulación</option></select></label><label className="field"><span>Formato de fechas</span><select value={dateFormat} onChange={e => setDateFormat(e.target.value)}><option value="iso">AAAA-MM-DD</option><option value="dmy">DD/MM/AAAA</option></select></label><label className="field"><span>Separador decimal</span><select value={decimalSeparator} onChange={e => setDecimalSeparator(e.target.value)}><option value=".">Punto (150.50)</option><option value=",">Coma (150,50)</option></select></label></div>
          <details className="mapping-details"><summary>Asignar columnas con nombres diferentes</summary><p className="small-muted">Indica el encabezado original y el campo al que corresponde. Las columnas con el nombre esperado no necesitan asignación.</p>{mapping.map((item, index) => <div key={index} className="mapping-row"><input aria-label={`Encabezado original ${index + 1}`} placeholder="Ej. documento" value={item.from} onChange={e => setMapping(rows => rows.map((row, i) => i === index ? { ...row, from: e.target.value } : row))}/><ArrowRight size={16}/><select aria-label={`Campo destino ${index + 1}`} value={item.to} onChange={e => setMapping(rows => rows.map((row, i) => i === index ? { ...row, to: e.target.value } : row))}><option value="">Campo de destino</option>{expectedFields.map(field => <option key={field} value={field}>{label(field)}</option>)}</select><button className="icon-button" type="button" aria-label={`Eliminar asignación ${index + 1}`} onClick={() => setMapping(rows => rows.filter((_, i) => i !== index))}><X size={17}/></button></div>)}<button className="text-button" type="button" onClick={() => setMapping(rows => [...rows, { from: '', to: '' }])}><Plus size={16}/>Agregar asignación</button></details>
          <button className="button primary full" disabled={!file || busy}>{busy ? 'Leyendo y validando…' : 'Validar y revisar archivo'}<ArrowRight size={18}/></button>
        </div></section>
        <aside className="import-guide"><section className="panel"><div className="panel-title"><h2>Así funciona la importación</h2></div><ol className="import-steps"><li><span>1</span><div><strong>Carga tu CSV</strong><p>Selecciona el área y el formato de tus datos.</p></div></li><li><span>2</span><div><strong>Revisa y corrige</strong><p>Consulta errores, advertencias y duplicados por fila.</p></div></li><li><span>3</span><div><strong>Confirma la importación</strong><p>Solo las filas elegibles pasan a los registros definitivos.</p></div></li></ol></section><section className="panel"><div className="panel-title"><h2>Columnas de {area === 'multas' ? 'multas' : 'pagos'}</h2></div><div className="column-tags">{expectedFields.map(field => <code key={field}>{field}{field === 'descripcion' ? ' (opcional)' : ''}</code>)}</div></section><Notice tone="info">{area === 'pagos' ? 'Importa primero las multas. Cada pago requiere una multa existente y un DNI coincidente.' : 'El estado declarado se contrasta con los pagos registrados. No se crearán pagos automáticamente.'}</Notice></aside>
      </form> : <section className="panel"><div className="panel-title"><h2>Historial de importaciones</h2><button className="icon-button" aria-label="Actualizar historial" onClick={() => setRefresh(n => n + 1)}><RefreshCw size={17}/></button></div>{loadingHistory ? <Spinner/> : !history.items.length ? <Empty title="Aún no hay importaciones" description="Al cargar tu primer CSV podrás seguir aquí su estado y retomar el borrador." action={<button className="button primary" onClick={() => setTab('new')}>Cargar archivo</button>}/> : <div className="table-scroll"><table><thead><tr><th>Archivo</th><th>Área</th><th>Estado</th><th>Creado por</th><th>Fecha</th><th>Importadas</th><th/></tr></thead><tbody>{history.items.map(item => <tr key={item.id}><td><button className="record-link" onClick={() => open(item.id)} disabled={busy}>{item.nombre_archivo}</button></td><td>{item.area === 'multas' ? 'Multas' : 'Pagos'}</td><td><Badge value={item.estado}/></td><td>{item.creado_por}</td><td>{date(item.created_at)}</td><td>{item.resumen?.importadas || 0}</td><td><button className="icon-button" title="Abrir importación" aria-label={`Abrir ${item.nombre_archivo}`} onClick={() => open(item.id)} disabled={busy}><Eye size={17}/></button></td></tr>)}</tbody></table></div>}<Pagination page={historyPage} total={history.total} pageSize={20} onChange={setHistoryPage} disabled={loadingHistory}/></section>}
    </> : <>
      <section className="batch-heading"><span className="file-icon"><FileSpreadsheet size={27}/></span><div><h2>{batch.nombre_archivo}</h2><p>{batch.area === 'multas' ? 'Multas' : 'Pagos'} · Creado por {batch.creado_por} · {date(batch.created_at)}</p></div><Badge value={batch.estado}/><button className="button secondary" disabled={busy} onClick={() => open(batch.id, batch.page || 1)}><RefreshCw size={16}/>Actualizar estado</button><button className="button secondary" onClick={download}><Download size={16}/>Reporte CSV</button></section>
      {batch.estado === 'CONFIRMADA' && <Notice tone="success"><strong>Importación completada.</strong> Se guardaron {summary?.importadas || 0} registros. Los errores y las exclusiones no se importaron.</Notice>}
      {batch.estado === 'BORRADOR' && <Notice tone="info">Estás revisando un borrador; aún no se han creado multas ni pagos. Caduca 24 horas después de su creación.</Notice>}
      {['CANCELADA', 'EXPIRADA'].includes(batch.estado) && <Notice tone="warning">Este lote está {batch.estado.toLowerCase()}. Sus datos temporales fueron eliminados y no se importaron registros.</Notice>}
      {batch.mensajes?.map((message, index) => <Notice key={index} tone="warning">{message}</Notice>)}
      <div className="import-summary"><div className="summary-card green"><span>Listas sin advertencias</span><strong>{summary?.listas || 0}</strong></div><div className="summary-card amber"><span>Listas con advertencias</span><strong>{summary?.advertencias || 0}</strong></div><div className="summary-card red"><span>Con errores</span><strong>{summary?.errores || 0}</strong></div><div className="summary-card gray"><span>Excluidas</span><strong>{summary?.excluidas || 0}</strong></div></div>
      <section className="panel"><div className="panel-title"><div><h2>Revisión de filas</h2><p>{summary?.vacias || 0} filas vacías omitidas · {batch.total_filas} filas leídas</p></div>{editable && <button className="button secondary" disabled={busy} onClick={() => operation('validar', 'Validación actualizada contra los registros actuales.')}><RefreshCw size={16}/>Volver a validar</button>}</div>
        {!batch.filas?.length ? <Empty title="No hay filas para mostrar" description={batch.estado === 'BORRADOR' ? 'El archivo no contiene registros importables.' : 'Consulta el resumen y el reporte del lote.'}/> : <div className="table-scroll"><table className="import-table"><thead><tr><th>Fila</th><th>Registro</th><th>Datos principales</th><th>Resultado</th><th>Observaciones</th>{editable && <th>Acciones</th>}</tr></thead><tbody>{batch.filas.map(row => <tr key={row.id} className={row.excluida ? 'excluded-row' : ''}><td className="row-number">{row.numero_fila}</td><td><strong className="mono">{row.datos.codigo_multa || 'Sin código'}</strong><small>DNI {row.datos.dni_infractor || 'sin completar'}</small>{batch.area === 'pagos' && <small>{row.datos.numero_comprobante || 'Sin comprobante'}</small>}</td><td>{batch.area === 'multas' ? <><span>{row.datos.tipo_infraccion || 'Sin tipo'}</span><small>Monto: {row.datos.monto || '—'} · {row.datos.fecha_infraccion || 'Sin fecha'}</small></> : <><span>{row.datos.metodo_pago || 'Sin método'}</span><small>Monto: {row.datos.monto_pagado || '—'} · {row.datos.fecha_pago || 'Sin fecha'}</small></>}</td><td><Badge value={row.resultado}/></td><td className="observations">{row.errores?.map((message, i) => <p className="text-red" key={`e${i}`}>{message}</p>)}{row.advertencias?.map((message, i) => <p className="text-amber" key={`a${i}`}>{message}</p>)}{!row.errores?.length && !row.advertencias?.length && <span className="small-muted">{row.resultado === 'IMPORTADA' ? 'Registro creado' : row.excluida ? 'Excluida de la importación' : 'Sin observaciones'}</span>}</td>{editable && <td><div className="row-actions"><button className="icon-button" aria-label={`Editar fila ${row.numero_fila}`} title="Corregir fila" disabled={busy} onClick={() => startEdit(row)}><Pencil size={17}/></button><button className="icon-button" aria-label={`${row.excluida ? 'Reincluir' : 'Excluir'} fila ${row.numero_fila}`} title={row.excluida ? 'Reincluir fila' : 'Excluir fila'} disabled={busy} onClick={() => toggleRow(row)}>{row.excluida ? <Plus size={17}/> : <Trash2 size={17}/>}</button></div></td>}</tr>)}</tbody></table></div>}
        <Pagination page={batch.page || 1} total={batch.total_filas} pageSize={batch.page_size || 50} disabled={busy} onChange={next => open(batch.id, next)}/>
      </section>
      {editable && <div className="confirmation-bar"><div><strong>{eligible} filas elegibles para importar</strong><p>{summary?.errores || 0} con errores y {summary?.excluidas || 0} excluidas quedarán fuera.</p></div><button className="button secondary danger-text" disabled={busy} onClick={() => setCanceling(true)}>Cancelar importación</button><button className="button primary" disabled={busy || !eligible} onClick={() => { setConfirming(true); setAccept(false); }}><Check size={18}/>Confirmar filas válidas</button></div>}
    </>}
    {editing && batch && <Modal title={`Corregir fila ${editing.numero_fila}`} subtitle="Los datos se volverán a validar antes de la importación." onClose={() => setEditing(null)} busy={busy} wide><form onSubmit={saveRow}><div className="modal-body"><div className="form-grid">{(batch.area === 'multas' ? [...fineFields.slice(0, 7), 'estado_multa', ...fineFields.slice(7)] : paymentFields).map(field => {
      const options = field === 'tipo_infraccion' ? catalogs.tipos_infraccion : field === 'metodo_pago' ? catalogs.metodos_pago : field === 'estado_multa' ? ['PENDIENTE', 'PARCIAL', 'PAGADA'].map(value => ({ codigo: value, nombre: value })) : null;
      return <label key={field} className={`field ${field === 'descripcion' ? 'span-2' : ''}`}><span>{label(field)}</span>{options ? <select value={editData[field] || ''} onChange={e => setEditData(d => ({ ...d, [field]: e.target.value }))}><option value="">Selecciona una opción</option>{editData[field] && !options.some(item => item.codigo === editData[field]) && <option value={editData[field]}>{editData[field]} (valor actual)</option>}{options.map(item => <option key={item.codigo} value={item.codigo}>{item.nombre}</option>)}</select> : field === 'descripcion' ? <textarea rows={2} value={editData[field] || ''} onChange={e => setEditData(d => ({ ...d, [field]: e.target.value }))}/> : <input value={editData[field] || ''} onChange={e => setEditData(d => ({ ...d, [field]: e.target.value }))} placeholder={field.startsWith('fecha_') ? 'Usa el formato elegido para el archivo' : undefined}/>}</label>;
    })}</div><p className="small-muted">Conserva el formato de fechas y decimales seleccionado al cargar el archivo. Guardar vuelve a incluir esta fila en la validación.</p>{editError && <Notice>{editError}</Notice>}</div><div className="modal-actions"><button type="button" className="button secondary" onClick={() => setEditing(null)} disabled={busy}>Cancelar</button><button className="button primary" disabled={busy}>{busy ? 'Validando…' : 'Guardar y validar fila'}</button></div></form></Modal>}
    {confirming && batch && <Modal title="Confirmar importación" subtitle="Revisa los totales antes de guardar." onClose={() => setConfirming(false)} busy={busy}><div className="modal-body"><div className="confirm-count"><CheckCircle2 size={32}/><strong>{eligible}</strong><span>registros se crearán en {batch.area === 'multas' ? 'Multas' : 'Pagos'}</span></div><p>Se incluyen {summary?.listas || 0} filas sin advertencias y {summary?.advertencias || 0} con advertencias.</p><Notice tone="info">Quedarán fuera {summary?.errores || 0} filas con errores y {summary?.excluidas || 0} excluidas. Si ocurre un error al guardar, no se importará ninguna fila de esta selección.</Notice><label className="checkbox-field"><input type="checkbox" checked={accept} onChange={e => setAccept(e.target.checked)}/>He revisado las advertencias y las filas que quedarán fuera.</label></div><div className="modal-actions"><button className="button secondary" disabled={busy} onClick={() => setConfirming(false)}>Volver a revisar</button><button className="button primary" disabled={busy || !accept} onClick={() => operation('confirmar', 'La importación se completó correctamente.', { aceptar_advertencias: true })}>{busy ? 'Guardando y verificando…' : 'Importar registros'}</button></div></Modal>}
    {canceling && <Modal title="Cancelar importación" subtitle="Los registros definitivos no serán modificados." onClose={() => setCanceling(false)} busy={busy}><div className="modal-body"><p>Se descartarán los datos temporales de este borrador. Para continuar más adelante tendrás que cargar el archivo otra vez.</p></div><div className="modal-actions"><button className="button secondary" disabled={busy} onClick={() => setCanceling(false)}>Seguir revisando</button><button className="button danger" disabled={busy} onClick={() => operation('cancelar', 'Importación cancelada. No se crearon registros.')}>{busy ? 'Cancelando…' : 'Descartar borrador'}</button></div></Modal>}
  </>;
}
