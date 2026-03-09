# Mobile (Capacitor) — Border Omni

## Stack

- **Capacitor 8** — bridge web → nativo
- **@capacitor/push-notifications** — notificações push
- **@capacitor/haptics** — feedback tátil
- **@capacitor/status-bar** — controle da status bar
- **@capacitor/splash-screen** — splash screen

---

## Configuração (capacitor.config.ts)

```typescript
{
  appId: 'com.borderomni.app',
  appName: 'Border Omni',
  webDir: 'dist',
  server: {
    // Descomente para apontar para o servidor de dev em device físico
    // url: 'http://192.168.1.XXX:9021',
    // cleartext: true,
  }
}
```

---

## Build Android

```bash
cd frontend

# 1. Build do frontend
npm run build

# 2. Sincronizar com projeto nativo
npm run mobile:sync
# ou: npx cap sync android

# 3. Abrir no Android Studio
npm run mobile:android
# ou: npx cap open android
```

O Android Studio abre e permite buildar o APK ou rodar no emulador/device.

---

## Build iOS

```bash
cd frontend

npm run build
npm run mobile:sync
npm run mobile:ios
# ou: npx cap open ios
```

Requer Xcode no macOS.

---

## Apontar para servidor de dev (device físico)

Para testar no celular físico apontando para o servidor local:

1. Descubra o IP da máquina: `ip addr show | grep 192.168`
2. Edite `frontend/capacitor.config.ts`:
   ```typescript
   server: {
     url: 'http://192.168.1.XXX:9021',
     cleartext: true,
   }
   ```
3. Garanta que o `start.sh` inicia o frontend com `--host 0.0.0.0`
4. Sincronize: `npx cap sync`

---

## Scripts disponíveis

```bash
npm run mobile:sync    # npx cap sync
npm run mobile:android # npx cap open android
npm run mobile:ios     # npx cap open ios
```

---

## Push Notifications (TODO)

Para ativar notificações push, é necessário:

1. Configurar o **Firebase Cloud Messaging (FCM)** para Android
2. Configurar **APNs** para iOS
3. No backend, criar endpoint para registrar device tokens
4. Enviar notificações quando um novo lead qualificado chegar

Referência: https://capacitorjs.com/docs/apis/push-notifications
