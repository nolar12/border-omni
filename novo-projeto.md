# Prompt — Novo Projeto ECS

Use este prompt no Cursor ao iniciar a configuração de um novo projeto.

---

## Prompt para setup do backend Django

```
Estou configurando um projeto Django para rodar no AWS ECS com Docker.

Arquitetura:
- ECS EC2 (não Fargate)
- Application Load Balancer com roteamento por host
- Backend Django + Gunicorn na porta 8000
- Banco de dados: Amazon RDS MySQL (externo ao container)
- Domínios: api.PROJETO.com.br e admin.PROJETO.com.br apontam para o mesmo service

Preciso que você:
1. Ajuste o settings.py com as configurações para ECS:
   - SECRET_KEY via variável de ambiente (sem fallback inseguro)
   - DEBUG=False por padrão
   - ALLOWED_HOSTS via variável de ambiente
   - CORS configurado para https://app.PROJETO.com.br
   - CSRF configurado para os domínios corretos
   - DATABASE conectando ao RDS MySQL via variáveis de ambiente

2. Adicione o endpoint /health em urls.py retornando status 200

3. Verifique o Dockerfile e entrypoint.sh:
   - Dockerfile com Python 3.12-slim
   - Usuário não-root
   - entrypoint.sh que aguarda o banco, roda migrate, collectstatic e inicia Gunicorn

4. Verifique o gunicorn.conf.py:
   - bind 0.0.0.0:8000 (obrigatório em containers ECS)
   - workers baseados no número de CPUs
   - logs para stdout/stderr

O nome do projeto é: PROJETO
O módulo WSGI está em: MODULO_WSGI.wsgi (ex: config.wsgi, myproject.wsgi)
```

---

## Prompt para setup do frontend React

```
Estou configurando um projeto React para rodar no AWS ECS com Docker.

Arquitetura:
- Build estático do React servido pelo Nginx
- Container roda na porta 80
- URL da API: https://api.PROJETO.com.br
- Variáveis de ambiente injetadas em runtime via env-config.js (não em build time)

Preciso que você:
1. Configure o Dockerfile multi-stage:
   - Stage 1: Node 20-alpine para build (npm ci + npm run build)
   - Stage 2: Nginx 1.27-alpine para servir o build

2. Configure o nginx.conf:
   - Servir arquivos de /usr/share/nginx/html
   - SPA fallback: try_files $uri $uri/ /index.html
   - Endpoint /health retornando 200
   - /env-config.js sem cache (no-store)
   - Cache longo para arquivos com hash no nome
   - Compressão gzip habilitada

3. Crie o entrypoint.sh que gera /usr/share/nginx/html/env-config.js com:
   window._env = { API_URL: "${API_URL}", APP_ENV: "${APP_ENV}" }

4. Adicione <script src="/env-config.js"></script> no index.html (antes do bundle)

5. Crie src/config.ts com:
   export const config = {
     apiUrl: (window as any)._env?.API_URL ?? import.meta.env.VITE_API_URL ?? "",
   }

O projeto usa: Vite (ou Create React App — informe qual)
```

---

## Prompt para gerar task definition ECS

```
Preciso gerar a task definition ECS para o projeto PROJETO.

Dados do projeto:
- Account ID: ACCOUNT_ID
- Region: REGION
- Cluster: PROJETO-cluster

Backend:
- Imagem: ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/backend:latest
- Porta do container: 8000
- CPU: 512, Memória: 1024 MB
- Log group: /ecs/PROJETO/backend
- Variáveis: DEBUG=False, ALLOWED_HOSTS=api.PROJETO.com.br,admin.PROJETO.com.br
- RDS Host: ENDPOINT_RDS
- Secrets no Secrets Manager: SECRET_KEY e DATABASE_PASSWORD

Frontend:
- Imagem: ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/frontend:latest
- Porta do container: 80
- CPU: 256, Memória: 512 MB
- Log group: /ecs/PROJETO/frontend
- Variável: API_URL=https://api.PROJETO.com.br

Gere os dois JSONs de task definition prontos para registrar com:
aws ecs register-task-definition --cli-input-json file://task-definition-backend.json
```
