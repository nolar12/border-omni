export const config = {
  apiUrl: (
    (window as any)._env?.API_URL ||
    import.meta.env.VITE_API_URL ||
    'http://localhost:9022'
  ).replace(/\/+$/, ''),
  appEnv: (window as any)._env?.APP_ENV || import.meta.env.MODE || 'development',
};
