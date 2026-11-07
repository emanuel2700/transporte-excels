import { useEffect, useState } from 'react';
import { ArrowRight, Banknote, CircleAlert, FileText, ReceiptText, UploadCloud, Wallet } from 'lucide-react';
import { api, errorMessage, money } from '../../lib/api';
import { Notice, Spinner } from '../../components/ui';
import type { DashboardData, Page } from '../../types';

export default function Dashboard({ username, navigate }: { username: string; navigate: (page: Page) => void }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  useEffect(() => { let active = true; setError(''); api<DashboardData>('/dashboard').then(value => { if (active) setData(value); }).catch(err => { if (active) setError(errorMessage(err)); }); return () => { active = false; }; }, [retry]);
  return <>
    <div className="page-heading"><div><span className="eyebrow">VISTA GENERAL</span><h1>Todo en un solo lugar</h1><p>Hola, {username}. Este es el estado de tus multas y cobranzas.</p></div><button className="button primary" onClick={() => navigate('importaciones')}><UploadCloud size={18}/>Importar CSV</button></div>
    {error && <Notice>{error} <button className="text-button" onClick={() => setRetry(n => n + 1)}>Reintentar</button></Notice>}
    {!data && !error ? <Spinner/> : data && <div className="stats-grid">
      <div className="stat-card"><span className="stat-icon blue"><FileText size={21}/></span><span className="stat-label">Multas registradas</span><strong>{data.multas.toLocaleString('es-PE')}</strong><small>{money(data.total_multas)} en multas vigentes</small></div>
      <div className="stat-card"><span className="stat-icon teal"><Banknote size={21}/></span><span className="stat-label">Total recaudado</span><strong>{money(data.total_pagado)}</strong><small>{data.pagos} pagos vigentes registrados</small></div>
      <div className="stat-card"><span className="stat-icon amber"><Wallet size={21}/></span><span className="stat-label">Saldo por cobrar</span><strong>{money(data.saldo_pendiente)}</strong><small>Importe pendiente de pago</small></div>
      <div className="stat-card"><span className="stat-icon red"><CircleAlert size={21}/></span><span className="stat-label">Multas vencidas</span><strong>{data.multas_vencidas}</strong><small>Con saldo y fecha de vencimiento superada</small></div>
    </div>}
    <section className="module-section"><div className="section-heading"><div><h2>Selecciona tu área de trabajo</h2><p>Cambia de módulo cuando lo necesites.</p></div><span className="small-muted">2 módulos disponibles</span></div><div className="module-grid">
      <button className="module-card" onClick={() => navigate('multas')}><span className="module-icon blue"><FileText size={28}/></span><span className="eyebrow">TRÁNSITO Y FISCALIZACIÓN</span><h3>Gestión de multas</h3><p>Registra infracciones, consulta expedientes y revisa su estado de cobranza.</p><span className="module-link">Abrir módulo<ArrowRight size={18}/></span></button>
      <button className="module-card" onClick={() => navigate('pagos')}><span className="module-icon teal"><ReceiptText size={28}/></span><span className="eyebrow">COBRANZAS</span><h3>Gestión de pagos</h3><p>Registra abonos, consulta comprobantes y sigue el saldo de cada multa.</p><span className="module-link">Abrir módulo<ArrowRight size={18}/></span></button>
    </div></section>
    <section className="import-banner"><div className="banner-icon"><UploadCloud size={30}/></div><div><h3>¿Tus registros están en archivos CSV?</h3><p>Cárgalos, revisa los resultados y corrige los datos antes de confirmar.</p></div><button className="button secondary" onClick={() => navigate('importaciones')}>Preparar importación<ArrowRight size={17}/></button></section>
    <p className="page-footnote">Los estados de cobranza se calculan con los pagos vigentes. Todos los importes se expresan en soles.</p>
  </>;
}
