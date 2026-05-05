const GOOGLE_CLIENT_ID: string =
  (window as any)._env?.GOOGLE_CLIENT_ID ||
  import.meta.env.VITE_GOOGLE_CLIENT_ID ||
  '';

export function useGoogleEnabled(): boolean {
  return Boolean(GOOGLE_CLIENT_ID);
}
