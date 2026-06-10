#!/usr/bin/env bash
# Border Omni — script de inicialização
# Frontend: http://localhost:9021
# Backend:  http://localhost:9022

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/venv"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
LOG_DIR="$ROOT/logs"

mkdir -p "$LOG_DIR"

# Carrega variáveis de ambiente do .env se existir
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT/.env"
  set +a
fi

# ─── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[border-omni]${NC} $*"; }
success() { echo -e "${GREEN}[border-omni]${NC} $*"; }
warn()    { echo -e "${YELLOW}[border-omni]${NC} $*"; }
error()   { echo -e "${RED}[border-omni]${NC} $*"; }

# ─── Kill any previous instances on those ports ────────────────────────────
kill_port() {
  local port=$1
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    local pid_list
    pid_list="$(echo "$pids" | tr '\n' ' ' | xargs)"
    warn "Porta $port em uso (PID(s): $pid_list). Encerrando..."
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
    sleep 1
  fi
}

port_http_ok() {
  local url=$1
  local pattern=$2
  curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -qE "$pattern"
}

save_port_pid() {
  local port=$1
  local pidfile=$2
  local pid
  pid="$(lsof -ti tcp:"$port" 2>/dev/null | head -n 1 || true)"
  if [ -n "$pid" ]; then
    echo "$pid" > "$pidfile"
  fi
}

pidfile_running() {
  local pidfile=$1
  if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    return 0
  fi
  return 1
}

# ─── Start backend ───────────────────────────────────────────────────────────
start_backend() {
  info "Iniciando backend Django na porta 9022..."
  if port_http_ok "http://127.0.0.1:9022/api/" "^(200|401|404|405)$"; then
    save_port_pid 9022 "$LOG_DIR/backend.pid"
    success "Backend já está ativo em http://localhost:9022"
    return
  fi

  kill_port 9022

  source "$VENV/bin/activate"

  # Update vite proxy to point to 9022 if needed (idempotent sed)
  sed -i "s|target: 'http://localhost:[0-9]*'|target: 'http://localhost:9022'|g" \
    "$FRONTEND/vite.config.ts" 2>/dev/null || true

  cd "$BACKEND"
  python manage.py runserver 127.0.0.1:9022 > "$LOG_DIR/backend.log" 2>&1 &
  BACKEND_PID=$!
  echo $BACKEND_PID > "$LOG_DIR/backend.pid"

  # Wait for backend to be ready
  local attempts=0
  while ! curl -s -o /dev/null -w "%{http_code}" http://localhost:9022/api/ 2>/dev/null | grep -qE "^(200|401|404|405)$"; do
    attempts=$((attempts+1))
    if [ $attempts -ge 15 ]; then
      error "Backend não respondeu em 15s. Verifique $LOG_DIR/backend.log"
      break
    fi
    sleep 1
  done

  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    error "Backend caiu durante a inicialização. Verifique $LOG_DIR/backend.log"
    return 1
  fi
  save_port_pid 9022 "$LOG_DIR/backend.pid"
  success "Backend rodando → http://localhost:9022  (log: logs/backend.log)"
}

# ─── Start frontend ──────────────────────────────────────────────────────────
start_frontend() {
  info "Iniciando frontend Vite na porta 9021..."
  if port_http_ok "http://127.0.0.1:9021/" "^200$"; then
    save_port_pid 9021 "$LOG_DIR/frontend.pid"
    success "Frontend já está ativo em http://localhost:9021"
    return
  fi

  kill_port 9021

  cd "$FRONTEND"
  npm run dev -- --host 127.0.0.1 --port 9021 --strictPort > "$LOG_DIR/frontend.log" 2>&1 &
  FRONTEND_PID=$!
  echo $FRONTEND_PID > "$LOG_DIR/frontend.pid"

  # Wait for frontend to be ready
  local attempts=0
  while ! curl -s -o /dev/null -w "%{http_code}" http://localhost:9021/ 2>/dev/null | grep -q "^200$"; do
    attempts=$((attempts+1))
    if [ $attempts -ge 20 ]; then
      error "Frontend não respondeu em 20s. Verifique $LOG_DIR/frontend.log"
      break
    fi
    sleep 1
  done

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    error "Frontend caiu durante a inicialização. Verifique $LOG_DIR/frontend.log"
    return 1
  fi
  save_port_pid 9021 "$LOG_DIR/frontend.pid"
  success "Frontend rodando → http://localhost:9021  (log: logs/frontend.log)"
}

NGROK_DOMAIN="${NGROK_DOMAIN:-borderomni.ngrok.app}"
ENABLE_NGROK="${ENABLE_NGROK:-false}"
SKIP_CELERY=false

# ─── Start ngrok ─────────────────────────────────────────────────────────────
# Expõe o backend (9022) diretamente — necessário para webhook do WhatsApp.
# O frontend buildado é servido pelo próprio Django, então um único túnel
# serve webhooks + API + app React pelo celular.
start_ngrok() {
  info "Iniciando ngrok com domínio fixo $NGROK_DOMAIN (→ porta 9022)..."
  # Para instância anterior (systemd-run ou processo direto)
  systemctl --user stop ngrok-borderomni.service 2>/dev/null || true
  pkill -f "ngrok http" 2>/dev/null || true
  sleep 1

  # systemd-run garante que o processo sobrevive mesmo quando a shell pai termina
  if systemd-run --user --unit=ngrok-borderomni \
      ngrok http 9022 --url="$NGROK_DOMAIN" --log=stdout \
      > "$LOG_DIR/ngrok.log" 2>&1; then
    # Salva o PID real para compatibilidade com stop_all
    sleep 2
    NGROK_PID=$(systemctl --user show ngrok-borderomni.service --property=MainPID --value 2>/dev/null || echo "")
    [ -n "$NGROK_PID" ] && echo "$NGROK_PID" > "$LOG_DIR/ngrok.pid"
  else
    warn "systemd-run não disponível, usando nohup..."
    nohup ngrok http 9022 --url="$NGROK_DOMAIN" --log=stdout \
      >> "$LOG_DIR/ngrok.log" 2>&1 &
    NGROK_PID=$!
    disown "$NGROK_PID"
    echo "$NGROK_PID" > "$LOG_DIR/ngrok.pid"
  fi

  sleep 5
  NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null)
  if [ -n "$NGROK_URL" ]; then
    success "Ngrok ativo → $NGROK_URL  (log: logs/ngrok.log)"
  else
    warn "Ngrok iniciado mas URL não detectada. Verifique logs/ngrok.log"
  fi
}

# ─── Start Celery worker ────────────────────────────────────────────────────
start_celery_worker() {
  info "Iniciando Celery worker..."
  if pidfile_running "$LOG_DIR/celery_worker.pid"; then
    success "Celery worker já está ativo (PID $(cat "$LOG_DIR/celery_worker.pid"))"
    return
  fi

  # Garante que o Redis está no ar — tenta iniciar silenciosamente se necessário
  if ! redis-cli ping > /dev/null 2>&1; then
    redis-server --daemonize yes --logfile "$LOG_DIR/redis.log" 2>/dev/null || true
    sleep 1
    if ! redis-cli ping > /dev/null 2>&1; then
      warn "Redis indisponível. Celery desativado. Rode: sudo systemctl enable --now redis-server"
      SKIP_CELERY=true
      return
    fi
  fi

  source "$VENV/bin/activate"
  cd "$BACKEND"

  # Kill any previous worker
  pkill -f "celery.*border_omni.*worker" 2>/dev/null || true
  sleep 1

  celery -A config worker \
    --loglevel=info \
    --concurrency=2 \
    -n "worker@%h" \
    > "$LOG_DIR/celery_worker.log" 2>&1 &
  CELERY_WORKER_PID=$!
  echo $CELERY_WORKER_PID > "$LOG_DIR/celery_worker.pid"
  success "Celery worker rodando (PID $CELERY_WORKER_PID) → log: logs/celery_worker.log"
}

# ─── Start Celery beat (scheduler) ─────────────────────────────────────────
start_celery_beat() {
  info "Iniciando Celery beat (agendador)..."
  if [ "$SKIP_CELERY" = "true" ]; then
    warn "Celery beat ignorado porque Redis está indisponível."
    return
  fi
  if pidfile_running "$LOG_DIR/celery_beat.pid"; then
    success "Celery beat já está ativo (PID $(cat "$LOG_DIR/celery_beat.pid"))"
    return
  fi

  source "$VENV/bin/activate"
  cd "$BACKEND"

  # Kill any previous beat
  pkill -f "celery.*border_omni.*beat" 2>/dev/null || true
  rm -f "$BACKEND/celerybeat-schedule" 2>/dev/null || true
  sleep 1

  celery -A config beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \
    > "$LOG_DIR/celery_beat.log" 2>&1 &
  CELERY_BEAT_PID=$!
  echo $CELERY_BEAT_PID > "$LOG_DIR/celery_beat.pid"
  success "Celery beat rodando (PID $CELERY_BEAT_PID) → log: logs/celery_beat.log"
}

# ─── Start watchdog ──────────────────────────────────────────────────────────
start_watchdog() {
  if systemctl --user is-active --quiet border-omni-watchdog.service 2>/dev/null; then
    success "Watchdog já está ativo."
  else
    info "Iniciando watchdog (systemd user service)..."
    systemctl --user start border-omni-watchdog.service 2>/dev/null || \
      warn "Watchdog não pôde ser iniciado via systemd. Rode: systemctl --user enable border-omni-watchdog.service"
    success "Watchdog ativo → log: /tmp/border_omni_watchdog.log"
  fi
}

# ─── Stop all ────────────────────────────────────────────────────────────────
stop_all() {
  info "Encerrando serviços..."
  systemctl --user stop border-omni-watchdog.service 2>/dev/null || true
  systemctl --user stop ngrok-borderomni.service 2>/dev/null || true

  # Evita depender de PID file stale: encerra por assinatura de comando.
  pkill -f "manage.py runserver 127.0.0.1:9022" 2>/dev/null || true
  pkill -f "vite.*--host 127.0.0.1.*--port 9021" 2>/dev/null || true
  pkill -f "celery.*-A config worker" 2>/dev/null || true
  pkill -f "celery.*-A config beat" 2>/dev/null || true
  pkill -f "ngrok http" 2>/dev/null || true

  rm -f "$LOG_DIR/backend.pid" "$LOG_DIR/frontend.pid" "$LOG_DIR/ngrok.pid" "$LOG_DIR/celery_worker.pid" "$LOG_DIR/celery_beat.pid"
  success "Serviços encerrados."
}

# ─── Main ────────────────────────────────────────────────────────────────────
case "${1:-start}" in
  start)
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║        Border Omni — Startup         ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
    echo ""
    start_backend
    start_celery_worker
    start_celery_beat
    start_frontend
    if [ "$ENABLE_NGROK" = "true" ]; then
      start_ngrok
    else
      info "Ngrok desativado (ENABLE_NGROK=false)."
    fi
    start_watchdog
    echo ""
    echo -e "${GREEN}✅ Sistema iniciado!${NC}"
    echo -e "   Frontend:  ${CYAN}http://localhost:9021${NC}"
    echo -e "   Backend:   ${CYAN}http://localhost:9022${NC}"
    echo -e "   Admin:     ${CYAN}http://localhost:9022/admin${NC}"
    echo -e "   Login:     marcello12souza@gmail.com  (senha no .env ou no seu gerenciador de senhas)"
    echo ""
    if [ "$ENABLE_NGROK" = "true" ]; then
      echo -e "   Acesso externo (celular/fora do Wi-Fi):"
      echo -e "   App:       ${CYAN}https://$NGROK_DOMAIN${NC}  ← rode ./start.sh build primeiro"
      echo -e "   WhatsApp:  ${CYAN}https://$NGROK_DOMAIN/api/webhooks/whatsapp/${NC}"
      echo -e "   Meta:      ${CYAN}https://$NGROK_DOMAIN/api/webhooks/meta/${NC}"
      echo ""
    fi
    echo -e "   Para encerrar: ${YELLOW}Ctrl+C  (ou ./start.sh stop em outro terminal)${NC}"
    echo ""
    echo -e "${CYAN}── Logs ao vivo (Ctrl+C para sair) ──────────────────────────────${NC}"
    trap 'echo ""; warn "Logs encerrados. Serviços continuam rodando em background."; exit 0' INT
    tail -f \
      "$LOG_DIR/backend.log" \
      "$LOG_DIR/celery_worker.log" \
      "$LOG_DIR/celery_beat.log" \
      "$LOG_DIR/frontend.log" \
      2>/dev/null
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    sleep 1
    exec "$ROOT/start.sh" start
    ;;
  status)
    echo ""
    if port_http_ok "http://127.0.0.1:9022/api/" "^(200|401|404|405)$"; then
      success "backend rodando"
    else
      warn "backend parado"
    fi
    if port_http_ok "http://127.0.0.1:9021/" "^200$"; then
      success "frontend rodando"
    else
      warn "frontend parado"
    fi
    if pidfile_running "$LOG_DIR/celery_worker.pid"; then
      success "celery_worker rodando (PID $(cat "$LOG_DIR/celery_worker.pid"))"
    else
      warn "celery_worker parado"
    fi
    if pidfile_running "$LOG_DIR/celery_beat.pid"; then
      success "celery_beat rodando (PID $(cat "$LOG_DIR/celery_beat.pid"))"
    else
      warn "celery_beat parado"
    fi
    echo ""
    ;;
  logs)
    echo -e "${CYAN}=== Backend ===${NC}"
    tail -20 "$LOG_DIR/backend.log" 2>/dev/null || echo "(sem log)"
    echo ""
    echo -e "${CYAN}=== Frontend ===${NC}"
    tail -20 "$LOG_DIR/frontend.log" 2>/dev/null || echo "(sem log)"
    echo ""
    echo -e "${CYAN}=== Celery Worker ===${NC}"
    tail -10 "$LOG_DIR/celery_worker.log" 2>/dev/null || echo "(sem log)"
    echo ""
    echo -e "${CYAN}=== Celery Beat ===${NC}"
    tail -10 "$LOG_DIR/celery_beat.log" 2>/dev/null || echo "(sem log)"
    ;;
  build)
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║     Border Omni — Build Frontend     ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
    echo ""
    info "Compilando frontend React..."
    cd "$FRONTEND" && npm run build
    success "Build concluído!"
    echo ""
    echo -e "   Acesse pelo celular/fora do Wi-Fi:"
    echo -e "   ${CYAN}https://$NGROK_DOMAIN${NC}"
    echo ""
    ;;
  *)
    echo "Uso: $0 {start|stop|restart|status|logs|build}"
    exit 1
    ;;
esac
