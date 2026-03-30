# Prompts — Deploy ECS Completo

Guia de prompts para configurar e fazer deploy de um projeto Django + React no AWS ECS com EC2.
Funciona para **projetos novos** (ainda sem código) e **projetos existentes** (já funcionando localmente).

Cada seção é um prompt independente, pronto para copiar e colar no Cursor.

---

## Placeholders — substitua antes de usar

| Placeholder | Exemplo | O que é |
|---|---|---|
| `PROJETO` | `filhotefacil` | Nome curto do projeto (sem espaços) |
| `DOMINIO` | `filhotefacil.com.br` | Domínio raiz |
| `ACCOUNT_ID` | `695455468842` | ID da conta AWS (12 dígitos) |
| `REGION` | `us-east-1` | Região AWS |
| `RDS_HOST` | `nolar-db-7.crsvmvzfe8dy.us-east-1.rds.amazonaws.com` | Endpoint do RDS compartilhado |
| `EC2_ID` | `i-0bc6ea50c858e95e4` | ID da instância EC2 do cluster ECS |
| `MODULO_WSGI` | `filhotefacil_backend` | Módulo Python do settings/wsgi (ex: `config`, `myproject`) |
| `CLUSTER` | `filhotefacil-cluster` | Nome do cluster ECS |

---

## Seção 1 — Setup do backend Django

```
Estou configurando um projeto Django para rodar no AWS ECS com Docker.

Stack e arquitetura:
- ECS EC2 (não Fargate), network mode: bridge
- Application Load Balancer (ALB) com roteamento por host header
- Backend Django + Gunicorn na porta 8000
- Banco de dados: Amazon RDS MySQL 8 (externo ao container, compartilhado entre projetos)
- Domínios: api.DOMINIO e admin.DOMINIO apontam para o mesmo ECS service

Preciso que você crie ou ajuste os seguintes arquivos:

1. requirements.txt — adicionar se não existirem:
   - gunicorn==21.2.0
   - PyMySQL==1.1.1
   - cryptography==42.0.5   ← obrigatório para MySQL 8 (caching_sha2_password auth)

2. settings.py — ajustes para ECS:
   - SECRET_KEY via env var sem fallback hardcoded (levantar RuntimeError se vazia)
   - DEBUG=False por padrão (ativar via env var)
   - ALLOWED_HOSTS via env var, incluindo * no valor (o ALB health checker envia o IP
     da instância EC2 como Host header — não o domínio — então * é necessário):
       ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1',
                               cast=lambda v: [s.strip() for s in v.split(',')])
   - CORS_ALLOWED_ORIGINS via env var para https://app.DOMINIO
   - CSRF_TRUSTED_ORIGINS via env var para os domínios corretos
   - DATABASE conectando ao RDS MySQL via env vars (DB_HOST, DB_PORT, DB_NAME,
     DB_USER, DB_PASSWORD) — usar PyMySQL:
       import pymysql
       pymysql.install_as_MySQLdb()

3. urls.py — adicionar endpoint /health:
   from django.http import HttpResponse
   def health(request):
       return HttpResponse('ok', content_type='text/plain', status=200)
   urlpatterns = [path('health', health), ...]

4. Dockerfile — Python 3.12-slim, usuário não-root:
   FROM python:3.12-slim
   ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
   WORKDIR /app
   RUN apt-get update && apt-get install -y --no-install-recommends \
       libjpeg-dev zlib1g-dev && rm -rf /var/lib/apt/lists/*
   RUN addgroup --system app && adduser --system --ingroup app app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   RUN mkdir -p staticfiles media && chown -R app:app /app
   RUN chmod +x entrypoint.sh
   USER app
   EXPOSE 8000
   ENTRYPOINT ["./entrypoint.sh"]

5. entrypoint.sh — aguarda MySQL com PyMySQL puro (sem cliente mysql instalado):
   #!/bin/bash
   set -e
   python - <<'PYEOF'
   import time, pymysql, os, sys
   host=os.environ.get("DB_HOST","localhost")
   port=int(os.environ.get("DB_PORT",3306))
   user=os.environ.get("DB_USER","")
   password=os.environ.get("DB_PASSWORD","")
   db=os.environ.get("DB_NAME","")
   for attempt in range(30):
       try:
           conn=pymysql.connect(host=host,port=port,user=user,password=password,db=db,connect_timeout=3)
           conn.close(); print("[entrypoint] MySQL pronto."); sys.exit(0)
       except Exception as e:
           print(f"[entrypoint] Tentativa {attempt+1}/30: {e}"); time.sleep(2)
   sys.exit(1)
   PYEOF
   echo "[entrypoint] ALLOWED_HOSTS: $ALLOWED_HOSTS"
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput --clear
   exec gunicorn MODULO_WSGI.wsgi:application --config gunicorn.conf.py

6. gunicorn.conf.py:
   import multiprocessing
   bind = "0.0.0.0:8000"   # obrigatório — 0.0.0.0 para o ALB alcançar o container
   workers = multiprocessing.cpu_count() * 2 + 1
   worker_class = "sync"
   timeout = 30
   keepalive = 2
   accesslog = "-"
   errorlog = "-"
   loglevel = "info"
   preload_app = True

O nome do projeto é: PROJETO
O módulo WSGI está em: MODULO_WSGI.wsgi
```

---

## Seção 2 — Setup do frontend React/Vite

```
Estou configurando um projeto React (Vite) para rodar no AWS ECS com Docker.

Arquitetura:
- Build estático servido pelo Nginx na porta 80
- URL da API injetada em runtime (não em build time) via env-config.js
- Rodando em ambiente com Podman (não Docker puro)

Preciso que você crie ou ajuste:

1. Dockerfile — multi-stage, atenção ao prefixo docker.io no Nginx (obrigatório no Podman):
   FROM node:20-alpine AS builder
   WORKDIR /app
   COPY package*.json ./
   RUN npm ci
   COPY . .
   RUN npx vite build   ← usar npx vite build, não npm run build (evita falhas de tsc no CI)
   
   FROM docker.io/nginx:1.27-alpine   ← prefixo docker.io obrigatório no Podman
   COPY --from=builder /app/dist /usr/share/nginx/html
   COPY nginx.conf /etc/nginx/conf.d/default.conf
   COPY entrypoint.sh /entrypoint.sh
   RUN chmod +x /entrypoint.sh
   EXPOSE 80
   ENTRYPOINT ["/entrypoint.sh"]

2. nginx.conf:
   server {
     listen 80;
     server_name _;
     root /usr/share/nginx/html;
     index index.html;
     gzip on; gzip_vary on; gzip_min_length 1024; gzip_proxied any;
     gzip_types text/plain text/css text/xml text/javascript
                application/javascript application/json image/svg+xml;

     location = /health {
       access_log off;
       return 200 "healthy\n";
       add_header Content-Type text/plain;
     }
     location = /env-config.js {
       add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
       add_header Pragma "no-cache";
       expires 0;
     }
     location ~* \.(js|css|woff|woff2|ttf|eot|ico|svg|png|jpg|jpeg|gif|webp)$ {
       expires 1y;
       add_header Cache-Control "public, immutable";
       try_files $uri =404;
     }
     location / {
       try_files $uri $uri/ /index.html;
     }
   }

3. entrypoint.sh — gera env-config.js em runtime:
   #!/bin/sh
   set -e
   cat > /usr/share/nginx/html/env-config.js <<EOF
   window._env = {
     API_URL: "${API_URL}",
     APP_ENV: "${APP_ENV}"
   };
   EOF
   exec nginx -g "daemon off;"

4. index.html — adicionar antes do bundle principal:
   <script src="/env-config.js"></script>

5. src/services/api.ts (ou onde estiver o axios/fetch base) — ler URL em runtime:
   const API_BASE_URL =
     (window as any)._env?.API_URL ||
     import.meta.env.VITE_API_URL ||
     'http://localhost:9012/api'

O projeto usa Vite. Domínio da API: https://api.DOMINIO/api
```

---

## Seção 3 — Infraestrutura AWS (pré-requisitos)

```
Preciso configurar a infraestrutura AWS para o projeto PROJETO antes do primeiro deploy.

Infraestrutura existente (compartilhada, não criar de novo):
- Cluster ECS: CLUSTER (EC2, já existe)
- RDS MySQL: RDS_HOST (já existe, banco e usuário serão criados na Seção 4)
- ALB: lb-nolar (já existe, listener 80 e 443 já existem)
- EC2 no cluster: EC2_ID

Execute os comandos abaixo para criar o que é específico deste projeto:

1. Repositórios ECR:
aws ecr create-repository --repository-name PROJETO/backend --region REGION
aws ecr create-repository --repository-name PROJETO/frontend --region REGION

2. Log groups CloudWatch:
aws logs create-log-group --log-group-name /ecs/PROJETO/backend  --region REGION
aws logs create-log-group --log-group-name /ecs/PROJETO/frontend --region REGION

3. Secrets Manager:
aws secretsmanager create-secret \
  --name PROJETO/backend/SECRET_KEY \
  --secret-string "$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')" \
  --region REGION

aws secretsmanager create-secret \
  --name PROJETO/backend/DB_PASSWORD \
  --secret-string "SENHA_GERADA_NA_SECAO_4" \
  --region REGION

4. IAM — inline policy no ecsTaskExecutionRole para ler os secrets:
   (o ecsTaskExecutionRole já existe; só adicionar a policy abaixo)
aws iam put-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-name PROJETO-secrets-access \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:PROJETO/*"
    }]
  }'

5. IAM — ecsTaskRole (se ainda não existir):
aws iam create-role \
  --role-name ecsTaskRole \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"ecs-tasks.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'
aws iam attach-role-policy \
  --role-name ecsTaskRole \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess

Account ID: ACCOUNT_ID
Region: REGION
```

---

## Seção 4 — Banco de dados RDS (usuário dedicado por projeto)

```
Preciso criar o banco de dados e um usuário MySQL dedicado para o projeto PROJETO
no RDS compartilhado, usando SSM para acessar a EC2 do cluster (sem precisar de
cliente MySQL local nem abrir portas).

Gere os comandos para fazer isso em duas etapas via AWS CLI:

Etapa 1 — gravar o script SQL na EC2 (via SSM send-command):
aws ssm send-command \
  --instance-ids "EC2_ID" \
  --document-name "AWS-RunShellScript" \
  --region REGION \
  --parameters 'commands=[
    "cat > /tmp/setup_PROJETO.sql << '"'"'ENDSQL'"'"'",
    "CREATE DATABASE IF NOT EXISTS PROJETO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
    "CREATE USER IF NOT EXISTS '"'"'PROJETO_user'"'"'@'"'"'%'"'"' IDENTIFIED BY '"'"'SENHA_AQUI'"'"';",
    "GRANT ALL PRIVILEGES ON PROJETO.* TO '"'"'PROJETO_user'"'"'@'"'"'%'"'"';",
    "FLUSH PRIVILEGES;",
    "SHOW DATABASES LIKE '"'"'PROJETO'"'"';",
    "SELECT user, host FROM mysql.user WHERE user='"'"'PROJETO_user'"'"';",
    "ENDSQL",
    "echo Script gravado"
  ]'

Etapa 2 — executar contra o RDS (via SSM, usando o usuário admin do RDS):
aws ssm send-command \
  --instance-ids "EC2_ID" \
  --document-name "AWS-RunShellScript" \
  --region REGION \
  --parameters 'commands=["mysql -h RDS_HOST -u admin --password='"'"'SENHA_ADMIN_RDS'"'"' < /tmp/setup_PROJETO.sql"]'

Etapa 3 — atualizar o secret DB_PASSWORD no Secrets Manager com a senha do PROJETO_user:
aws secretsmanager update-secret \
  --secret-id "PROJETO/backend/DB_PASSWORD" \
  --secret-string "SENHA_AQUI" \
  --region REGION

Gerar uma senha segura sem metacaracteres de shell:
python3 -c "import secrets,string; chars=string.ascii_letters+string.digits; print(''.join(secrets.choice(chars) for _ in range(28))+'Xx1!')"

Dados:
- RDS: RDS_HOST (MySQL 8, usuário admin do RDS com senha SENHA_ADMIN_RDS)
- Banco a criar: PROJETO
- Usuário a criar: PROJETO_user
- EC2 do cluster: EC2_ID
- Region: REGION
```

---

## Seção 5 — Task Definitions ECS

```
Preciso gerar as task definitions ECS para o projeto PROJETO.

Pontos críticos aprendidos em produção:
- networkMode: bridge (não awsvpc — instâncias EC2 compartilhadas)
- hostPort: 0 (dynamic port mapping — o ECS escolhe a porta no host)
- ALLOWED_HOSTS deve incluir * porque o ALB health checker envia o IP da instância
  EC2 como Host header HTTP, não o domínio
- startPeriod: 60 no healthCheck do backend (as migrations levam tempo)
- secrets via valueFrom com ARN completo do Secrets Manager
- taskRoleArn é necessário além do executionRoleArn

Gere os dois JSONs abaixo:

BACKEND (ecs/task-definition-backend.json):
{
  "family": "PROJETO-backend",
  "networkMode": "bridge",
  "requiresCompatibilities": ["EC2"],
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskRole",
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [{
    "name": "backend",
    "image": "ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/backend:latest",
    "essential": true,
    "portMappings": [{"containerPort": 8000, "hostPort": 0, "protocol": "tcp"}],
    "environment": [
      {"name": "DEBUG",                "value": "False"},
      {"name": "ALLOWED_HOSTS",        "value": "api.DOMINIO,admin.DOMINIO,*"},
      {"name": "CORS_ALLOWED_ORIGINS", "value": "https://app.DOMINIO"},
      {"name": "CSRF_TRUSTED_ORIGINS", "value": "https://api.DOMINIO,https://admin.DOMINIO,https://app.DOMINIO"},
      {"name": "DB_NAME",              "value": "PROJETO"},
      {"name": "DB_USER",              "value": "PROJETO_user"},
      {"name": "DB_HOST",              "value": "RDS_HOST"},
      {"name": "DB_PORT",              "value": "3306"}
    ],
    "secrets": [
      {"name": "SECRET_KEY",   "valueFrom": "ARN_SECRET_KEY"},
      {"name": "DB_PASSWORD",  "valueFrom": "ARN_DB_PASSWORD"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/PROJETO/backend",
        "awslogs-region": "REGION",
        "awslogs-stream-prefix": "ecs"
      }
    },
    "healthCheck": {
      "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
      "interval": 30,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 60
    }
  }]
}

FRONTEND (ecs/task-definition-frontend.json):
{
  "family": "PROJETO-frontend",
  "networkMode": "bridge",
  "requiresCompatibilities": ["EC2"],
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole",
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [{
    "name": "frontend",
    "image": "ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/frontend:latest",
    "essential": true,
    "portMappings": [{"containerPort": 80, "hostPort": 0, "protocol": "tcp"}],
    "environment": [
      {"name": "API_URL",  "value": "https://api.DOMINIO/api"},
      {"name": "APP_ENV",  "value": "production"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/PROJETO/frontend",
        "awslogs-region": "REGION",
        "awslogs-stream-prefix": "ecs"
      }
    },
    "healthCheck": {
      "command": ["CMD-SHELL", "wget -qO- http://localhost/health || exit 1"],
      "interval": 30,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 10
    }
  }]
}

Após gerar, registrar com:
aws ecs register-task-definition --cli-input-json file://ecs/task-definition-backend.json --region REGION
aws ecs register-task-definition --cli-input-json file://ecs/task-definition-frontend.json --region REGION

Dados do projeto:
- PROJETO: PROJETO
- DOMINIO: DOMINIO
- ACCOUNT_ID: ACCOUNT_ID
- REGION: REGION
- RDS_HOST: RDS_HOST
```

---

## Seção 6 — DNS e Certificado HTTPS

```
Preciso configurar DNS no Route 53 e certificado HTTPS no ACM para o projeto PROJETO
com domínio DOMINIO.

O ALB compartilhado já existe (lb-nolar) com listener 443 configurado.

Execute em ordem:

PASSO 1 — Verificar se o domínio está apontando para Route 53 (CRÍTICO):
O nameserver registrado no registrador DEVE bater com o NS da hosted zone.
Se bater, o ACM consegue validar. Se não bater, a validação trava indefinidamente.

# Verificar o que o registrador tem:
dig @b0.nic.io DOMINIO NS

# Verificar o que a hosted zone do Route 53 tem:
aws route53 list-resource-record-sets \
  --hosted-zone-id HOSTED_ZONE_ID \
  --query "ResourceRecordSets[?Type=='NS'].ResourceRecords[*].Value" \
  --output text

Se forem diferentes: ir ao registrador (Hostinger, GoDaddy, etc.) e atualizar
os nameservers para os da hosted zone do Route 53. Aguardar propagação (5-60 min).

PASSO 2 — Criar registros A Alias no Route 53:
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name --dns-name DOMINIO \
  --query "HostedZones[0].Id" --output text | cut -d/ -f3)

ALB_DNS=$(aws elbv2 describe-load-balancers --region REGION \
  --query "LoadBalancers[?LoadBalancerName=='lb-nolar'].DNSName" --output text)

ALB_ZONE=$(aws elbv2 describe-load-balancers --region REGION \
  --query "LoadBalancers[?LoadBalancerName=='lb-nolar'].CanonicalHostedZoneId" --output text)

aws route53 change-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --change-batch "{
    \"Changes\": [
      {\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"app.DOMINIO\",\"Type\":\"A\",\"AliasTarget\":{\"HostedZoneId\":\"$ALB_ZONE\",\"DNSName\":\"$ALB_DNS\",\"EvaluateTargetHealth\":true}}},
      {\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"api.DOMINIO\",\"Type\":\"A\",\"AliasTarget\":{\"HostedZoneId\":\"$ALB_ZONE\",\"DNSName\":\"$ALB_DNS\",\"EvaluateTargetHealth\":true}}},
      {\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"admin.DOMINIO\",\"Type\":\"A\",\"AliasTarget\":{\"HostedZoneId\":\"$ALB_ZONE\",\"DNSName\":\"$ALB_DNS\",\"EvaluateTargetHealth\":true}}}
    ]
  }"

PASSO 3 — Solicitar certificado ACM wildcard e validar via DNS:
CERT_ARN=$(aws acm request-certificate \
  --domain-name "*.DOMINIO" \
  --subject-alternative-names "DOMINIO" \
  --validation-method DNS \
  --region REGION \
  --query "CertificateArn" --output text)

# Obter o CNAME de validação:
aws acm describe-certificate --certificate-arn "$CERT_ARN" --region REGION \
  --query "Certificate.DomainValidationOptions[0].{Nome:ResourceRecord.Name,Valor:ResourceRecord.Value}"

# Criar o CNAME no Route 53 (substituir NOME e VALOR pelo output acima):
aws route53 change-resource-record-sets \
  --hosted-zone-id "$HOSTED_ZONE_ID" \
  --change-batch '{"Changes":[{"Action":"UPSERT","ResourceRecordSet":{
    "Name":"NOME_CNAME_ACM",
    "Type":"CNAME","TTL":300,
    "ResourceRecords":[{"Value":"VALOR_CNAME_ACM"}]
  }}]}'

# Aguardar validação (pode levar 5-30 min após DNS propagar):
aws acm wait certificate-validated --certificate-arn "$CERT_ARN" --region REGION

PASSO 4 — Adicionar certificado ao listener 443 do ALB:
LISTENER_443=$(aws elbv2 describe-listeners \
  --load-balancer-arn $(aws elbv2 describe-load-balancers --region REGION \
    --query "LoadBalancers[?LoadBalancerName=='lb-nolar'].LoadBalancerArn" --output text) \
  --region REGION \
  --query "Listeners[?Port==\`443\`].ListenerArn" --output text)

aws elbv2 add-listener-certificates \
  --listener-arn "$LISTENER_443" \
  --certificates CertificateArn="$CERT_ARN" \
  --region REGION

Dados:
- DOMINIO: DOMINIO
- REGION: REGION
- ALB: lb-nolar
```

---

## Seção 7 — Build, Deploy e Verificação

```
Preciso fazer o build, push e deploy do projeto PROJETO no ECS e verificar se está
funcionando corretamente.

PASSO 1 — Login no ECR:
aws ecr get-login-password --region REGION \
  | docker login --username AWS \
    --password-stdin ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com

PASSO 2 — Build e push das imagens:
# Backend
docker build -t PROJETO/backend ./PASTA_BACKEND
docker tag PROJETO/backend:latest ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/backend:latest
docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/backend:latest

# Frontend
docker build -t PROJETO/frontend ./PASTA_FRONTEND
docker tag PROJETO/frontend:latest ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/frontend:latest
docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/frontend:latest

PASSO 3 — Forçar novo deployment:
aws ecs update-service --cluster CLUSTER --service backend-service  --force-new-deployment --region REGION
aws ecs update-service --cluster CLUSTER --service frontend-service --force-new-deployment --region REGION

PASSO 4 — Verificar health dos targets no ALB (esperar ~2-3 min):
# Ver ARNs dos target groups:
aws elbv2 describe-target-groups --region REGION \
  --query "TargetGroups[*].{Nome:TargetGroupName,ARN:TargetGroupArn}" --output table

# Verificar saúde:
aws elbv2 describe-target-health --target-group-arn ARN_BACKEND_TG --region REGION \
  --query "TargetHealthDescriptions[*].{Port:Target.Port,State:TargetHealth.State}" --output table

aws elbv2 describe-target-health --target-group-arn ARN_FRONTEND_TG --region REGION \
  --query "TargetHealthDescriptions[*].{Port:Target.Port,State:TargetHealth.State}" --output table

# Estado esperado: State = healthy

PASSO 5 — Ver logs do backend (últimas linhas):
STREAM=$(aws logs describe-log-streams \
  --log-group-name /ecs/PROJETO/backend \
  --region REGION --order-by LastEventTime --descending --max-items 1 \
  --query "logStreams[0].logStreamName" --output text)

aws logs get-log-events \
  --log-group-name /ecs/PROJETO/backend \
  --log-stream-name "$STREAM" \
  --region REGION --limit 30 \
  --query "events[*].message" --output text

# No log deve aparecer em sequência:
# [entrypoint] MySQL pronto.
# Running migrations: ...
# [entrypoint] Iniciando Gunicorn...
# Listening at: http://0.0.0.0:8000

PASSO 6 — Verificar migrations aplicadas no banco via SSM:
aws ssm send-command \
  --instance-ids "EC2_ID" \
  --document-name "AWS-RunShellScript" \
  --region REGION \
  --parameters 'commands=["mysql -h RDS_HOST -u PROJETO_user -pSENHA_DB PROJETO -e \"SHOW TABLES; SELECT app,name,applied FROM django_migrations ORDER BY app,name;\""]'

# Verificar resultado:
aws ssm get-command-invocation \
  --command-id CMD_ID --instance-id EC2_ID --region REGION \
  --query "StandardOutputContent" --output text

Dados do projeto:
- PROJETO: PROJETO
- CLUSTER: CLUSTER
- ACCOUNT_ID: ACCOUNT_ID
- REGION: REGION
- EC2_ID: EC2_ID
- RDS_HOST: RDS_HOST
```

---

## Seção 8 — CI/CD com GitHub Actions (deploy automático)

```
Preciso configurar deploy automático no projeto PROJETO via GitHub Actions.

A cada push ou merge na branch main, o workflow deve:
1. Build das imagens Docker de backend e frontend
2. Push para o ECR com duas tags: :latest e :<git-sha>
3. Force new deployment nos services ECS
4. Aguardar estabilização (health check)
5. Se falhar: rollback automático para a task definition anterior

Crie o arquivo .github/workflows/deploy.yml com dois jobs paralelos
(deploy-backend e deploy-frontend), cada um com a lógica de rollback.

O rollback funciona assim:
- Antes do deploy, salva a task definition atual com:
    aws ecs describe-services --query "services[0].taskDefinition"
- Após o deploy, roda:
    aws ecs wait services-stable
- Se o wait falhar (continue-on-error: true), volta para a task definition salva
- Finaliza com exit 1 para marcar o workflow como falho e notificar por email

Secrets necessários no GitHub (Settings → Secrets → Actions):
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION         → ex: us-east-1
- ECS_CLUSTER        → ex: PROJETO-cluster

Estrutura de pastas do projeto:
- Backend em: ./PASTA_BACKEND   (ex: ./habit-backend)
- Frontend em: ./PASTA_FRONTEND (ex: ./habit-frontend)

ECR repos:
- Backend:  ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/backend
- Frontend: ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/PROJETO/frontend

ECS services:
- backend-service
- frontend-service

Dados do projeto:
- PROJETO: PROJETO
- ACCOUNT_ID: ACCOUNT_ID
- REGION: REGION
- CLUSTER: CLUSTER
- PASTA_BACKEND: PASTA_BACKEND
- PASTA_FRONTEND: PASTA_FRONTEND
```

---

## Referência rápida — Lições aprendidas

| Problema | Causa | Solução |
|---|---|---|
| Health check retorna 400 | ALB envia IP da EC2 como Host header | Incluir `*` no `ALLOWED_HOSTS` |
| `cryptography package required` | MySQL 8 usa `caching_sha2_password` | Adicionar `cryptography==42.0.5` ao requirements |
| `Access denied for user` | Usuário sem permissão ou senha errada | Criar usuário dedicado via SSM (Seção 4) |
| ACM preso em PENDING_VALIDATION | NS do registrador diferente da hosted zone | Atualizar NS no registrador (Seção 6, Passo 1) |
| Build falha com erros TypeScript | `npm run build` roda `tsc` explicitamente | Usar `npx vite build` no Dockerfile |
| Nginx falha no pull da imagem | Podman exige nome completo da imagem | Usar `docker.io/nginx:1.27-alpine` |
| `ecsTaskRole` não assumível | Role não existe ou trust policy errada | Criar role com trust para `ecs-tasks.amazonaws.com` |
| Secrets Manager AccessDenied | Managed policy não suficiente | Adicionar inline policy específica ao `ecsTaskExecutionRole` |
| Log stream não encontrado | Task falhou antes de criar o stream | Checar tasks paradas: `aws ecs list-tasks --desired-status STOPPED` |
