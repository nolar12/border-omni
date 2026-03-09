import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { authService } from '../services/auth';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await authService.login(email, password);
      navigate('/dashboard');
    } catch {
      setError('Email ou senha inválidos.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div data-theme="border_omni" className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-blue-500 flex items-center justify-center mx-auto mb-4 shadow-lg">
            <span className="text-white text-2xl font-bold">B</span>
          </div>
          <h1 className="text-2xl font-bold text-white">Border Omni</h1>
          <p className="text-slate-400 text-sm mt-1">Qualificação de leads via WhatsApp</p>
        </div>
        <div className="bg-white rounded-2xl shadow-xl p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Entrar</h2>
          {error && (
            <div className="flex items-center gap-2 bg-red-50 text-red-600 text-sm rounded-lg px-3 py-2 mb-4">
              <span>⚠️</span><span>{error}</span>
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" placeholder="seu@email.com"
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm outline-none focus:border-blue-400 transition-colors"
                value={email} onChange={e => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Senha</label>
              <input type="password" placeholder="••••••••"
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm outline-none focus:border-blue-400 transition-colors"
                value={password} onChange={e => setPassword(e.target.value)} required />
            </div>
            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold rounded-xl py-2.5 text-sm transition-colors flex items-center justify-center gap-2">
              {loading ? <span className="loading loading-spinner loading-sm" /> : 'Entrar'}
            </button>
          </form>
        </div>
        <p className="text-center text-slate-500 text-xs mt-4">
          admin@bordercollie.com / admin123
        </p>
      </div>
    </div>
  );
}
