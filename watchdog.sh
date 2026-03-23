#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Border Omni — Watchdog
#  Monitora backend (9022), frontend (9021) e ngrok.
#  Reinicia automaticamente qualquer serviço que cair.
#  Gerenciado via: systemctl --user {start|stop|status} border-omni-watchdog.service
# ─────────────────────────────────────────────────────────────

BACKEND_PORT=9022
FRONTEND_PORT=9021
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="/tmp/border_omni_watchdog.log"
CHECK_INTERVAL=20   # segundos entre cada verificação

# Caminhos absolutos — necessário quando rodando via systemd (PATH mínimo)
NPM_BIN="/home/marcellosouza/.nvm/versions/node/v24.14.0/bin/npm"
NGROK_BIN="/home/marcellosouza/.local/bin/ngrok"

mkdir -p "$LOG_DIR"

# Carrega variáveis de ambiente do .env se existir
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$PROJECT_DIR/.env"
  set +a
fi

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ─── Backend ─────────────────────────────────────────────────
start_backend() {
  log "⚡ Iniciando backend na porta $BACKEND_PORT..."
  pkill -f "runserver 0.0.0.0:$BACKEND_PORT" 2>/dev/null || true
  sleep 1
  cd "$BACKEND_DIR" && source "$VENV_DIR/bin/activate" && \
    nohup python manage.py runserver "0.0.0.0:$BACKEND_PORT" \
      >> "$LOG_DIR/backend.log" 2>&1 &
  BACKEND_PID=$!
  disown "$BACKEND_PID"
  echo "$BACKEND_PID" > "$LOG_DIR/backend.pid"
  sleep 3
  log "✅ Backend iniciado (PID: $BACKEND_PID)"
}

is_backend_alive() {
  curl -s -o /dev/null -w "%{http_code}" \
    --connect-timeout 3 --max-time 5 \
    "http://localhost:$BACKEND_PORT/api/leads/" 2>/dev/null | grep -qE "^(200|401|403)"
}

# ─── Frontend ────────────────────────────────────────────────
start_frontend() {
  log "⚡ Iniciando frontend na porta $FRONTEND_PORT..."
  pkill -f "vite.*$FRONTEND_PORT" 2>/dev/null || true
  sleep 1
  cd "$FRONTEND_DIR" && \
    nohup "$NPM_BIN" run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" \
      >> "$LOG_DIR/frontend.log" 2>&1 &
  FRONTEND_PID=$!
  disown "$FRONTEND_PID"
  echo "$FRONTEND_PID" > "$LOG_DIR/frontend.pid"
  # Aguarda até 30s pelo frontend ficar pronto (npm/vite leva tempo no cold boot)
  local attempts=0
  while [ $attempts -lt 15 ]; do
    sleep 2
    attempts=$((attempts + 1))
    if is_frontend_alive; then
      log "✅ Frontend pronto em $((attempts * 2))s (PID: $FRONTEND_PID)"
      return 0
    fi
  done
  log "⚠️  Frontend não respondeu em 30s — pode ainda estar carregando."
}

is_frontend_alive() {
  curl -s -o /dev/null -w "%{http_code}" \
    --connect-timeout 3 --max-time 5 \
    "http://localhost:$FRONTEND_PORT/" 2>/dev/null | grep -q "^200$"
}

# ─── Ngrok ───────────────────────────────────────────────────
NGROK_DOMAIN="borderomni.ngrok.app"
NGROK_PORT=$BACKEND_PORT

start_ngrok() {
  log "🌐 Iniciando ngrok com domínio fixo $NGROK_DOMAIN (→ porta $NGROK_PORT)..."
  systemctl --user stop ngrok-borderomni.service 2>/dev/null || true
  pkill -f "ngrok http" 2>/dev/null || true
  sleep 1

  nohup "$NGROK_BIN" http "$NGROK_PORT" --url="$NGROK_DOMAIN" --log=stdout \
    >> /tmp/ngrok.log 2>&1 &
  NGROK_PID=$!
  disown "$NGROK_PID"

  sleep 6

  NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null)

  if [ -n "$NGROK_URL" ]; then
    log "✅ Ngrok ativo: $NGROK_URL"
    log "   WhatsApp webhook : $NGROK_URL/api/webhooks/whatsapp/"
    log "   Meta webhook     : $NGROK_URL/api/webhooks/meta/"
  else
    log "⚠️  Ngrok iniciado mas URL não detectada ainda."
  fi
}

is_ngrok_alive() {
  curl -s --connect-timeout 3 http://localhost:4040/api/tunnels 2>/dev/null | grep -q "public_url"
}

# ─── Inicialização ───────────────────────────────────────────
log "════════════════════════════════════"
log " Border Omni Watchdog iniciado"
log " Projeto : $PROJECT_DIR"
log " Intervalo de check: ${CHECK_INTERVAL}s"
log "════════════════════════════════════"

is_backend_alive  || start_backend
is_frontend_alive || start_frontend
is_ngrok_alive    || start_ngrok

BACKEND_RESTARTS=0
FRONTEND_RESTARTS=0
NGROK_RESTARTS=0

# ─── Loop principal ──────────────────────────────────────────
while true; do
  sleep "$CHECK_INTERVAL"

  if ! is_backend_alive; then
    BACKEND_RESTARTS=$((BACKEND_RESTARTS + 1))
    log "🔴 Backend caiu! Reiniciando... (tentativa #$BACKEND_RESTARTS)"
    start_backend
    if is_backend_alive; then
      log "✅ Backend recuperado."
    else
      log "❌ Backend não respondeu após reinício."
    fi
  fi

  if ! is_frontend_alive; then
    FRONTEND_RESTARTS=$((FRONTEND_RESTARTS + 1))
    log "🔴 Frontend caiu! Reiniciando... (tentativa #$FRONTEND_RESTARTS)"
    start_frontend
    if is_frontend_alive; then
      log "✅ Frontend recuperado."
    else
      log "❌ Frontend não respondeu após reinício."
    fi
  fi

  if ! is_ngrok_alive; then
    NGROK_RESTARTS=$((NGROK_RESTARTS + 1))
    log "🔴 Ngrok caiu! Reiniciando... (tentativa #$NGROK_RESTARTS)"
    start_ngrok
  fi

done
