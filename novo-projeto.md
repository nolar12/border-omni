# Prompt — Novo Projeto ECS

Use este prompt no Cursor ao iniciar a configuração de um novo projeto.

## Valores fixos desta conta AWS

| Campo | Valor |
|-------|-------|
| Account ID | `695455468842` |
| Region | `us-east-1` |
| RDS Host compartilhado | `nolar-db-7.crsvmvzfe8dy.us-east-1.rds.amazonaws.com` |
| Task Execution Role ARN | `arn:aws:iam::695455468842:role/ecsTaskExecutionRole` |
| Task Role ARN | `arn:aws:iam::695455468842:role/ecsTaskRole` |
| EC2 Instance Role | `ecsInstanceRole` |

> **Antes de começar:** crie os secrets no Secrets Manager:
> ```bash
> # Substitua PROJETO pelo nome do projeto (ex: meusite)
> aws secretsmanager create-secret \
>   --name PROJETO/backend/SECRET_KEY \
>   --secret-string "$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
>
> aws secretsmanager create-secret \
>   --name PROJETO/backend/DB_PASSWORD \
>   --secret-string "SENHA_DO_BANCO"
> ```
> Os ARNs gerados terão o formato:
> `arn:aws:secretsmanager:us-east-1:695455468842:secret:PROJETO/backend/SECRET_KEY-XXXXXX`

---

## Prompt para setup do backend Django

```
Estou configurando um projeto Django para rodar no AWS ECS com Docker.

Arquitetura:
- ECS EC2 (não Fargate) — conta AWS 695455468842, região us-east-1
- Application Load Balancer com roteamento por host
- Backend Django + Gunicorn na porta 8000
- Banco de dados: Amazon RDS MySQL compartilhado
  Host: nolar-db-7.crsvmvzfe8dy.us-east-1.rds.amazonaws.com
- Domínios: api.PROJETO.com.br e admin.PROJETO.com.br apontam para o mesmo service

Preciso que você:
1. Ajuste o settings.py com as configurações para ECS:
   - SECRET_KEY via variável de ambiente (sem fallback inseguro)
   - DEBUG=False por padrão
   - ALLOWED_HOSTS via variável de ambiente
   - CORS configurado para os domínios do projeto
   - CSRF configurado para os domínios corretos
   - DATABASE conectando ao RDS MySQL via variáveis de ambiente

2. Adicione o endpoint /health em urls.py retornando status 200

3. Verifique o Dockerfile e entrypoint.sh:
   - Dockerfile com Python 3.12-slim
   - Usuário não-root
   - entrypoint.sh com shebang #!/bin/sh (não bash)
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

## Prompt para gerar task definitions ECS

```
Preciso gerar as task definitions ECS para o projeto PROJETO.

Dados fixos da conta:
- Account ID: 695455468842
- Region: us-east-1
- Cluster: PROJETO-cluster
- Task Execution Role: arn:aws:iam::695455468842:role/ecsTaskExecutionRole
- Task Role: arn:aws:iam::695455468842:role/ecsTaskRole
- RDS Host compartilhado: nolar-db-7.crsvmvzfe8dy.us-east-1.rds.amazonaws.com

Backend:
- Imagem: 695455468842.dkr.ecr.us-east-1.amazonaws.com/PROJETO/backend:latest
- Porta do container: 8000
- CPU: 512, Memória: 768 MB
- Log group: /ecs/PROJETO/backend
- Variáveis: DEBUG=False, ALLOWED_HOSTS=api.PROJETO.com.br,admin.PROJETO.com.br
- DB_NAME: PROJETO_db, DB_USER: PROJETO_user
- Secrets Manager (ARNs gerados ao criar os secrets):
  - SECRET_KEY: arn:aws:secretsmanager:us-east-1:695455468842:secret:PROJETO/backend/SECRET_KEY-XXXXXX
  - DB_PASSWORD: arn:aws:secretsmanager:us-east-1:695455468842:secret:PROJETO/backend/DB_PASSWORD-XXXXXX

Frontend:
- Imagem: 695455468842.dkr.ecr.us-east-1.amazonaws.com/PROJETO/frontend:latest
- Porta do container: 80
- CPU: 256, Memória: 512 MB
- Log group: /ecs/PROJETO/frontend
- Variável: API_URL=https://api.PROJETO.com.br

Gere os dois JSONs de task definition prontos para registrar com:
aws ecs register-task-definition --cli-input-json file://task-definition-backend.json
```

---

## Checklist de infraestrutura para novo projeto

- [ ] Criar repositórios ECR: `aws ecr create-repository --repository-name PROJETO/backend` e `/frontend`
- [ ] Criar secrets no Secrets Manager: `PROJETO/backend/SECRET_KEY` e `PROJETO/backend/DB_PASSWORD`
- [ ] Criar banco no RDS: `CREATE DATABASE PROJETO_db; CREATE USER 'PROJETO_user'@'%' IDENTIFIED BY '...'; GRANT ALL ON PROJETO_db.* TO 'PROJETO_user'@'%';`
- [ ] Criar cluster ECS: `aws ecs create-cluster --cluster-name PROJETO-cluster`
- [ ] Lançar EC2 `t3.small` com user-data apontando para `PROJETO-cluster` e IAM role `ecsInstanceRole`
- [ ] Criar Target Groups no ALB (um por serviço)
- [ ] Adicionar regras de host no ALB Listener HTTPS (porta 443)
- [ ] Criar serviços ECS (backend e frontend) apontando para os Target Groups
- [ ] Certificado ACM para `*.PROJETO.com.br` + adicionar ao listener do ALB
- [ ] Route 53: criar hosted zone e apontar para o ALB
