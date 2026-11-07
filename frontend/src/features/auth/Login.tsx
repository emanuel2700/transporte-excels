import { useState, type FormEvent } from 'react';
import { ArrowRight, FileCheck2, Route, ShieldCheck, UserRound, LockKeyhole } from 'lucide-react';
import { api, errorMessage, json } from '../../lib/api';
import { Notice } from '../../components/ui';

export default function Login({ onLogin }: { onLogin: (name: string) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true);
    try { const result = await api<{ username: string }>('/auth/login', { method: 'POST', body: json({ username, password }) }); setPassword(''); onLogin(result.username); }
    catch (err) { setError(errorMessage(err)); } finally { setBusy(false); }
  }
  return <main className="login-layout">
    <section className="login-story"><a className="brand" href="#inicio"><span className="brand-mark"><Route size={27}/></span><span>Vía<span className="brand-light">Control</span><small>GESTIÓN DE TRANSPORTE</small></span></a>
      <div className="login-copy"><span className="eyebrow light">MULTAS · COBRANZAS · REGISTROS</span><h1>Una ruta clara<br/>para tus registros.</h1><p>Centraliza las multas, registra los pagos y transforma tus archivos CSV en información organizada.</p><div className="login-benefits"><span><FileCheck2 size={21}/> Importación con revisión previa</span><span><ShieldCheck size={21}/> Historial de cada operación</span></div></div>
      <p className="login-footer">Plataforma de gestión · Prueba de concepto</p>
    </section>
    <section className="login-form-side"><div className="login-card"><span className="pill">ACCESO DE DEMOSTRACIÓN</span><h2>Bienvenido a VíaControl</h2><p>Ingresa un nombre para identificar tus registros.</p>
      <Notice tone="info">Este acceso acepta cualquier usuario y contraseña no vacíos. El nombre se registra como identidad declarada; no se verifica. Usa una contraseña ficticia.</Notice>
      <form onSubmit={submit}><label className="field"><span>Nombre de usuario</span><div className="input-icon"><UserRound size={18}/><input autoComplete="username" autoFocus required maxLength={80} value={username} onChange={e => setUsername(e.target.value)} placeholder="Ej. María López"/></div></label>
        <label className="field"><span>Contraseña de demostración</span><div className="input-icon"><LockKeyhole size={18}/><input type="password" autoComplete="off" required value={password} onChange={e => setPassword(e.target.value)} placeholder="Escribe cualquier contraseña"/></div></label>
        {error && <Notice>{error}</Notice>}<button className="button primary full" disabled={busy || !username.trim() || !password.trim()}>{busy ? 'Ingresando…' : 'Ingresar a la plataforma'}<ArrowRight size={18}/></button>
      </form><p className="small-muted">La contraseña no se almacena. Ambos módulos estarán disponibles.</p>
    </div></section>
  </main>;
}
