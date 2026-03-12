#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Border Omni — Watchdog
#  Monitora backend (porta 9022) e ngrok, reinicia se caírem.
#  Uso: bash watchdog.sh
#  Para rodar em background: nohup bash watchdog.sh &
# ─────────────────────────────────────────────────────────────

BACKEND_PORT=9022
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$PROJECT_DIR/venv"
LOG_FILE="/tmp/border_omni_watchdog.log"
BACKEND_LOG="/tmp/backend.log"
CHECK_INTERVAL=20   # segundos entre cada verificação

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

start_backend() {
  log "⚡ Iniciando backend na porta $BACKEND_PORT..."
  pkill -f "runserver 0.0.0.0:$BACKEND_PORT" 2>/dev/null
  sleep 1
  cd "$BACKEND_DIR" && source "$VENV_DIR/bin/activate" && \
    nohup python manage.py runserver "0.0.0.0:$BACKEND_PORT" >> "$BACKEND_LOG" 2>&1 &
  sleep 3
  log "✅ Backend iniciado (PID: $!)"
}

start_ngrok() {
  log "🌐 Iniciando ngrok na porta $BACKEND_PORT..."
  pkill -f "ngrok http" 2>/dev/null
  sleep 1
  nohup ngrok http "$BACKEND_PORT" --log=stdout >> /tmp/ngrok.log 2>&1 &
  sleep 4

  NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null)

  if [ -n "$NGROK_URL" ]; then
    log "✅ Ngrok ativo: $NGROK_URL"
  else
    log "⚠️  Ngrok iniciado mas URL não detectada ainda."
  fi
}

is_backend_alive() {
  curl -s -o /dev/null -w "%{http_code}" \
    --connect-timeout 3 --max-time 5 \
    "http://localhost:$BACKEND_PORT/api/leads/" 2>/dev/null | grep -qE "^(200|401|403)"
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

is_backend_alive || start_backend
is_ngrok_alive   || start_ngrok

BACKEND_RESTARTS=0
NGROK_RESTARTS=0

# ─── Loop principal ──────────────────────────────────────────
while true; do
  sleep "$CHECK_INTERVAL"

  if ! is_backend_alive; then
    BACKEND_RESTARTS=$((BACKEND_RESTARTS + 1))
    log "🔴 Backend caiu! Reiniciando... (tentativa #$BACKEND_RESTARTS)"
    start_backend
    if is_backend_alive; then
      log "✅ Backend recuperado com sucesso."
    else
      log "❌ Backend não respondeu após reinício."
    fi
  fi

  if ! is_ngrok_alive; then
    NGROK_RESTARTS=$((NGROK_RESTARTS + 1))
    log "🔴 Ngrok caiu! Reiniciando... (tentativa #$NGROK_RESTARTS)"
    start_ngrok
  fi

done
