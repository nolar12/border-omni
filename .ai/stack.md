# Stack — border_omni

## Backend
| Pacote | Versão | Uso |
|--------|--------|-----|
| Django | 4.2.20 | Framework web |
| djangorestframework | 3.15.2 | API REST |
| djangorestframework-simplejwt | 5.3.1 | JWT auth |
| django-cors-headers | 4.3.1 | CORS |
| django-filter | 24.3 | Filtros DRF |
| PyMySQL | 1.1.1 | Driver MySQL |
| openai | 1.56.2 | IA (qualificação, RAG) |
| supabase | 2.9.1 | RAG vetorial |
| weasyprint | 62.3 | PDF contratos |
| gunicorn | 21.2.0 | Servidor produção |
| Pillow | 10.4.0 | Imagens |
| boto3 | 1.35.76 | AWS S3 |
| django-storages | 1.14.4 | S3 storage backend |
| requests | 2.32.3 | HTTP |
| cryptography | 42.0.5 | Criptografia (tokens em repouso com Fernet) |
| celery | 5.4.0 | Filas de tasks assíncronas |
| redis | 5.2.1 | Broker Celery |
| django-celery-beat | 2.7.0 | Agendamento de tasks periódicas (DB scheduler) |
| pypdf | 4.3.1 | Leitura/preenchimento de PDF AcroForm (registro de ninhada) |

## Celery
- Broker: Redis (`redis://127.0.0.1:6379/0`)
- Scheduler: `django_celery_beat.schedulers:DatabaseScheduler`
- Tasks registradas: `sync_whatsapp_quality_ratings` (a cada 6h)
- Worker iniciado via `start.sh` → logs em `logs/celery_worker.log`
- Beat iniciado via `start.sh` → logs em `logs/celery_beat.log`

## Variáveis de ambiente novas (2025-05)
```
REDIS_URL=redis://127.0.0.1:6379/0
FIELD_ENCRYPTION_KEY=<gerar com Fernet.generate_key()>
META_APP_ID=
META_APP_SECRET=
META_CONFIG_ID_WHATSAPP=
META_CONFIG_ID_FACEBOOK=
META_CONFIG_ID_INSTAGRAM=
META_WEBHOOK_BASE_URL=
```

## Frontend
| Pacote | Versão | Uso |
|--------|--------|-----|
| react | ^19.2.0 | UI |
| vite | ^7.3.1 | Build |
| typescript | ~5.9.3 | Linguagem |
| react-router-dom | ^6.30.3 | Rotas |
| axios | ^1.13.6 | HTTP client |
| tailwindcss | ^4.2.1 | CSS |
| daisyui | ^5.5.19 | Componentes UI |
| @capacitor/core | ^8.x | Mobile |
| vite-plugin-pwa | ^1.2.0 | PWA |

## Banco de dados
- MySQL — banco `border_leads`, host localhost, porta 3306

## Variáveis de ambiente
```
SECRET_KEY=
DEBUG=False
DB_NAME=border_leads
DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=3306
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_KEY=
AWS_STORAGE_BUCKET_NAME=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

## Portas de desenvolvimento
- Backend: 9022
- Frontend: 9021
