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
| cryptography | 42.0.5 | Criptografia |

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
