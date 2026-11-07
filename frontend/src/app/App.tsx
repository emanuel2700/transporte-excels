import { useEffect, useState } from 'react';
import { LayoutDashboard, FileText, ReceiptText, UploadCloud, LogOut, Route, Menu, X, ChevronRight } from 'lucide-react';
import { api, ApiError, errorMessage } from '../lib/api';
import { Notice, Spinner } from '../components/ui';
import Login from '../features/auth/Login';
import Dashboard from '../features/dashboard/Dashboard';
import Records from '../features/records/Records';
import Imports from '../features/importaciones/Imports';
import type { Catalogs, Page } from '../types';

const navigation = [
  { id: 'inicio' as const, name: 'Vista general', icon: LayoutDashboard },
  { id: 'multas' as const, name: 'Multas', icon: FileText },
  { id: 'pagos' as const, name: 'Pagos', icon: ReceiptText },
  { id: 'importaciones' as const, name: 'Importaciones', icon: UploadCloud },
];
const readPage = (): Page => navigation.some(item => item.id === window.location.hash.slice(1)) ? window.location.hash.slice(1) as Page : 'inicio';

export default function App() {
  const [username, setUsername] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [page, setPage] = useState<Page>(readPage);
  const [menu, setMenu] = useState(false);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const [catalogs, setCatalogs] = useState<Catalogs>({ tipos_infraccion: [], metodos_pago: [] });
  useEffect(() => {
    let active = true; setError(''); setInitializing(true);
    api<{ username: string }>('/auth/me').then(result => { if (active) setUsername(result.username); }).catch(err => { if (active && !(err instanceof ApiError && err.status === 401)) setError(errorMessage(err)); }).finally(() => { if (active) setInitializing(false); });
    return () => { active = false; };
  }, [retry]);
  useEffect(() => { const expire = () => { setUsername(null); setError('Tu sesión terminó. Ingresa de nuevo para continuar.'); }; const hash = () => setPage(readPage()); window.addEventListener('session-expired', expire); window.addEventListener('hashchange', hash); return () => { window.removeEventListener('session-expired', expire); window.removeEventListener('hashchange', hash); }; }, []);
  useEffect(() => { if (username) api<Catalogs>('/catalogos').then(setCatalogs).catch(err => setError(errorMessage(err))); }, [username]);
  function navigate(next: Page) { window.location.hash = next; setPage(next); setMenu(false); window.scrollTo(0, 0); }
  async function logout() { try { await api('/auth/logout', { method: 'POST' }); setUsername(null); setError(''); navigate('inicio'); } catch (err) { setError(errorMessage(err)); } }
  if (initializing) return <div className="app-start"><Route size={44}/><Spinner text="Preparando tu espacio de trabajo…"/></div>;
  if (!username) return <>{error && <div className="login-error"><Notice>{error}<button className="text-button" onClick={() => setRetry(n => n + 1)}>Reintentar conexión</button></Notice></div>}<Login onLogin={name => { setUsername(name); setError(''); }}/></>;
  return <div className="app-shell">
    {menu && <button className="sidebar-backdrop" aria-label="Cerrar menú" onClick={() => setMenu(false)}/>}
    <aside className={`sidebar ${menu ? 'open' : ''}`}><a className="brand" href="#inicio" onClick={() => setMenu(false)}><span className="brand-mark"><Route size={25}/></span><span>Vía<span className="brand-light">Control</span><small>GESTIÓN DE TRANSPORTE</small></span></a><button className="sidebar-close icon-button" aria-label="Cerrar menú" onClick={() => setMenu(false)}><X size={20}/></button>
      <span className="nav-label">ESPACIO DE TRABAJO</span><nav aria-label="Navegación principal">{navigation.map(item => <a key={item.id} href={`#${item.id}`} className={page === item.id ? 'active' : ''} onClick={() => navigate(item.id)}><item.icon size={19}/><span>{item.name}</span>{page === item.id && <ChevronRight size={16}/>}</a>)}</nav>
      <div className="sidebar-note"><span className="status-dot"/><strong>Entorno de demostración</strong><p>Multas y cobranzas en una plataforma centralizada.</p></div><div className="sidebar-version">VíaControl <span>v0.1 · POC</span></div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-menu" aria-label="Abrir menú" onClick={() => setMenu(true)}><Menu size={22}/></button><span>Plataforma</span><ChevronRight size={14}/><strong>{navigation.find(item => item.id === page)?.name}</strong></div><div className="user-menu"><span className="demo-tag">DEMO</span><span className="avatar">{username.slice(0, 2).toUpperCase()}</span><div className="user-name"><strong>{username}</strong><small>Usuario declarado</small></div><button className="icon-button" aria-label="Cerrar sesión" title="Cerrar sesión" onClick={logout}><LogOut size={18}/></button></div></header>
      <main className="content">{error && <Notice>{error}</Notice>}{page === 'inicio' ? <Dashboard username={username} navigate={navigate}/> : page === 'importaciones' ? <Imports catalogs={catalogs}/> : <Records key={page} area={page} catalogs={catalogs} navigate={navigate}/>}</main>
    </div>
  </div>;
}
