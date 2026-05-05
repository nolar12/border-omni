import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useGoogleLogin } from '@react-oauth/google';
import { authService } from '../services/auth';
import { useGoogleEnabled } from '../hooks/useGoogleEnabled';

export default function Register() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const googleEnabled = useGoogleEnabled();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('As senhas não conferem.');
      return;
    }
    if (password.length < 6) {
      setError('A senha deve ter pelo menos 6 caracteres.');
      return;
    }

    setLoading(true);
    try {
      await authService.register({ name, email, phone, password });
      navigate('/dashboard');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Erro ao criar conta. Tente novamente.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  const loginWithGoogle = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      setGoogleLoading(true);
      setError('');
      try {
        await authService.googleLogin(tokenResponse.access_token);
        navigate('/dashboard');
      } catch (err: any) {
        const msg = err?.response?.data?.detail || 'Erro ao autenticar com Google.';
        setError(msg);
      } finally {
        setGoogleLoading(false);
      }
    },
    onError: () => {
      setError('Falha na autenticação com Google.');
      setGoogleLoading(false);
    },
  });

  return (
    <div
      data-theme="light"
      className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 p-4"
    >
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-blue-500 flex items-center justify-center mx-auto mb-4 shadow-lg">
            <span className="text-white text-2xl font-bold">B</span>
          </div>
          <h1 className="text-3xl font-bold text-white">Border Omni</h1>
          <p className="text-slate-400 text-base mt-1">Qualificação de leads via WhatsApp</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl p-6">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">Criar conta</h2>

          {error && (
            <div className="flex items-center gap-2 bg-red-50 text-red-600 text-sm rounded-lg px-3 py-2 mb-4">
              <span>⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* Google OAuth — só mostra se VITE_GOOGLE_CLIENT_ID estiver configurado */}
          {googleEnabled && (
            <>
              <button
                type="button"
                onClick={() => { setError(''); loginWithGoogle(); }}
                disabled={googleLoading || loading}
                className="w-full flex items-center justify-center gap-3 border border-gray-200 rounded-xl py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60 transition-colors mb-4"
              >
                {googleLoading ? (
                  <span className="loading loading-spinner loading-sm" />
                ) : (
                  <GoogleIcon />
                )}
                Continuar com Google
              </button>
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-1 h-px bg-gray-200" />
                <span className="text-xs text-gray-400">ou</span>
                <div className="flex-1 h-px bg-gray-200" />
              </div>
            </>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nome completo</label>
              <input
                type="text"
                placeholder="Seu nome"
                className="w-full border border-gray-200 rounded-xl px-3 py-3 text-sm text-gray-900 bg-white outline-none focus:border-blue-400 transition-colors"
                value={name}
                onChange={e => setName(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                placeholder="seu@email.com"
                className="w-full border border-gray-200 rounded-xl px-3 py-3 text-sm text-gray-900 bg-white outline-none focus:border-blue-400 transition-colors"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Telefone <span className="text-gray-400 font-normal">(opcional)</span>
              </label>
              <input
                type="tel"
                placeholder="(51) 99999-9999"
                className="w-full border border-gray-200 rounded-xl px-3 py-3 text-sm text-gray-900 bg-white outline-none focus:border-blue-400 transition-colors"
                value={phone}
                onChange={e => setPhone(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Senha</label>
              <input
                type="password"
                placeholder="Mínimo 6 caracteres"
                className="w-full border border-gray-200 rounded-xl px-3 py-3 text-sm text-gray-900 bg-white outline-none focus:border-blue-400 transition-colors"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirmar senha</label>
              <input
                type="password"
                placeholder="Repita a senha"
                className="w-full border border-gray-200 rounded-xl px-3 py-3 text-sm text-gray-900 bg-white outline-none focus:border-blue-400 transition-colors"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading || googleLoading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold rounded-xl py-3 text-sm transition-colors flex items-center justify-center gap-2 mt-1"
            >
              {loading ? <span className="loading loading-spinner loading-sm" /> : 'Criar conta'}
            </button>
          </form>
        </div>

        <p className="text-center text-slate-400 text-sm mt-4">
          Já tem uma conta?{' '}
          <Link to="/login" className="text-blue-400 hover:text-blue-300 font-medium">
            Entrar
          </Link>
        </p>
      </div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"
        fill="#4285F4"
      />
      <path
        d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"
        fill="#34A853"
      />
      <path
        d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z"
        fill="#FBBC05"
      />
      <path
        d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z"
        fill="#EA4335"
      />
    </svg>
  );
}
