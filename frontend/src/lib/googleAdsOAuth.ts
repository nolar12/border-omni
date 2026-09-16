// Google Identity Services popup ("code client") — mesma arquitetura já usada
// para o Meta via window.FB.login(): abre um popup, recebe um authorization
// code, o backend troca por refresh_token (nunca expomos client_secret no
// frontend). Extraído para cá porque tanto PromoteCampaignModal (conectar
// pela primeira vez, com seleção de conta) quanto o botão "Atualizar
// permissões" da tela de Anúncios (reautorizar a conta já conectada) usam o
// mesmo popup — só o que acontece depois do code muda.
declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initCodeClient(config: {
            client_id: string;
            scope: string;
            ux_mode: 'popup';
            callback: (response: { code?: string; error?: string }) => void;
          }): { requestCode(): void };
        };
      };
    };
  }
}

export const GOOGLE_ADS_CLIENT_ID = import.meta.env.VITE_GOOGLE_ADS_CLIENT_ID as string | undefined;

// adwords: gestão de campanhas/métricas. datamanager: envio de conversões
// (QUALIFIED/RESERVED/SOLD) via Data Manager API — substituta da antiga
// uploadClickConversions, descontinuada para novos adotantes desde 2026-06-15.
export const GOOGLE_ADS_OAUTH_SCOPE = 'https://www.googleapis.com/auth/adwords https://www.googleapis.com/auth/datamanager';

let gisScriptLoading = false;

export function loadGoogleIdentityServices(onLoad: () => void) {
  if (window.google?.accounts?.oauth2) { onLoad(); return; }
  if (gisScriptLoading) {
    const check = setInterval(() => {
      if (window.google?.accounts?.oauth2) { clearInterval(check); onLoad(); }
    }, 200);
    return;
  }
  gisScriptLoading = true;
  const script = document.createElement('script');
  script.src = 'https://accounts.google.com/gsi/client';
  script.async = true;
  script.defer = true;
  script.onload = onLoad;
  document.body.appendChild(script);
}

/** Abre o popup do Google e entrega o authorization code (ou um erro) via callback. */
export function requestGoogleAdsAuthCode(onCode: (code: string) => void, onError: (message: string) => void) {
  if (!GOOGLE_ADS_CLIENT_ID) {
    onError('VITE_GOOGLE_ADS_CLIENT_ID não configurado no .env do frontend.');
    return;
  }
  loadGoogleIdentityServices(() => {
    const client = window.google!.accounts.oauth2.initCodeClient({
      client_id: GOOGLE_ADS_CLIENT_ID,
      scope: GOOGLE_ADS_OAUTH_SCOPE,
      ux_mode: 'popup',
      callback: (response) => {
        if (!response.code) {
          onError('Autorização cancelada ou negada.');
          return;
        }
        onCode(response.code);
      },
    });
    client.requestCode();
  });
}
