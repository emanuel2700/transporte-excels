import { useEffect, useId, useRef, type ReactNode } from 'react';
import { AlertCircle, CheckCircle2, ChevronLeft, ChevronRight, LoaderCircle, X, Inbox } from 'lucide-react';

export function Notice({ children, tone = 'error' }: { children: ReactNode; tone?: 'error' | 'success' | 'info' | 'warning' }) {
  return <div className={`notice ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>{tone === 'success' ? <CheckCircle2 size={18}/> : <AlertCircle size={18}/>}<div>{children}</div></div>;
}
export function Spinner({ text = 'Cargando información…' }: { text?: string }) {
  return <div className="loading" role="status"><LoaderCircle className="spin" size={24}/><span>{text}</span></div>;
}
export function Empty({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="empty"><span className="empty-icon"><Inbox size={30}/></span><h3>{title}</h3><p>{description}</p>{action}</div>;
}
export function Badge({ value }: { value: string }) {
  const color = ['PAGADA', 'CONFIRMADA', 'IMPORTADA', 'VALIDA'].includes(value) ? 'green' : ['PARCIAL', 'ADVERTENCIA', 'BORRADOR'].includes(value) ? 'amber' : ['ERROR', 'ANULADO', 'VENCIDA'].includes(value) ? 'red' : 'gray';
  return <span className={`badge ${color}`}><i/>{value.replaceAll('_', ' ').toLowerCase()}</span>;
}
export function Modal({ title, subtitle, children, onClose, wide = false, busy = false }: { title: string; subtitle?: string; children: ReactNode; onClose: () => void; wide?: boolean; busy?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const subtitleId = useId();
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    const before = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { dialog.close(); document.body.style.overflow = before; };
  }, []);
  return <dialog ref={ref} aria-labelledby={titleId} aria-describedby={subtitle ? subtitleId : undefined} className={`modal ${wide ? 'wide' : ''}`} onCancel={event => { event.preventDefault(); if (!busy) closeRef.current(); }}>
    <div className="modal-head"><div><h2 id={titleId}>{title}</h2>{subtitle && <p id={subtitleId}>{subtitle}</p>}</div><button className="icon-button" aria-label="Cerrar diálogo" disabled={busy} onClick={onClose}><X size={22}/></button></div>
    {children}
  </dialog>;
}
export function Pagination({ page, total, pageSize, onChange, disabled = false }: { page: number; total: number; pageSize: number; onChange: (page: number) => void; disabled?: boolean }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return <div className="pagination"><span>{total === 0 ? '0 registros' : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} de ${total} registros`}</span><div><button className="icon-button" aria-label="Página anterior" disabled={disabled || page <= 1} onClick={() => onChange(page - 1)}><ChevronLeft size={18}/></button><span>{page} / {pages}</span><button className="icon-button" aria-label="Página siguiente" disabled={disabled || page >= pages} onClick={() => onChange(page + 1)}><ChevronRight size={18}/></button></div></div>;
}
