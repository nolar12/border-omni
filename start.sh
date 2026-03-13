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
  local pid
  pid=$(lsof -ti tcp:"$port" 2>/dev/null || true)
  if [ -n "$pid" ]; then
    warn "Porta $port em uso (PID $pid). Encerrando..."
    kill -9 "$pid" 2>/dev/null || true
    sleep 1
  fi
}

# ─── Start backend ───────────────────────────────────────────────────────────
start_backend() {
  info "Iniciando backend Django na porta 9022..."
  kill_port 9022

  source "$VENV/bin/activate"

  # Update vite proxy to point to 9022 if needed (idempotent sed)
  sed -i "s|target: 'http://localhost:[0-9]*'|target: 'http://localhost:9022'|g" \
    "$FRONTEND/vite.config.ts" 2>/dev/null || true

  cd "$BACKEND"
  python manage.py runserver 0.0.0.0:9022 > "$LOG_DIR/backend.log" 2>&1 &
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

  success "Backend rodando → http://localhost:9022  (log: logs/backend.log)"
}

# ─── Start frontend ──────────────────────────────────────────────────────────
start_frontend() {
  info "Iniciando frontend Vite na porta 9021..."
  kill_port 9021

  cd "$FRONTEND"
  npm run dev -- --host 0.0.0.0 --port 9021 > "$LOG_DIR/frontend.log" 2>&1 &
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

  success "Frontend rodando → http://localhost:9021  (log: logs/frontend.log)"
}

NGROK_DOMAIN="borderomni.ngrok.app"

# ─── Start ngrok ─────────────────────────────────────────────────────────────
start_ngrok() {
  info "Iniciando ngrok com domínio fixo $NGROK_DOMAIN..."
  pkill -f "ngrok http" 2>/dev/null
  sleep 1
  ngrok http 9022 --url="$NGROK_DOMAIN" > "$LOG_DIR/ngrok.log" 2>&1 &
  NGROK_PID=$!
  echo $NGROK_PID > "$LOG_DIR/ngrok.pid"
  sleep 6
  NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])" 2>/dev/null)
  if [ -n "$NGROK_URL" ]; then
    success "Ngrok ativo → $NGROK_URL  (log: logs/ngrok.log)"
  else
    warn "Ngrok iniciado mas URL não detectada. Verifique logs/ngrok.log"
  fi
}

# ─── Stop all ────────────────────────────────────────────────────────────────
stop_all() {
  info "Encerrando serviços..."
  for pidfile in "$LOG_DIR/backend.pid" "$LOG_DIR/frontend.pid" "$LOG_DIR/ngrok.pid"; do
    if [ -f "$pidfile" ]; then
      pid=$(cat "$pidfile")
      kill "$pid" 2>/dev/null && info "PID $pid encerrado" || true
      rm -f "$pidfile"
    fi
  done
  pkill -f "ngrok http" 2>/dev/null || true
  kill_port 9021
  kill_port 9022
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
    start_frontend
    start_ngrok
    echo ""
    echo -e "${GREEN}✅ Sistema iniciado!${NC}"
    echo -e "   Frontend:  ${CYAN}http://localhost:9021${NC}"
    echo -e "   Backend:   ${CYAN}http://localhost:9022${NC}"
    echo -e "   Admin:     ${CYAN}http://localhost:9022/admin${NC}"
    echo -e "   Login:     marcello12souza@gmail.com / admin123"
    echo ""
    echo -e "   Webhooks públicos (ngrok fixo):"
    echo -e "   WhatsApp:  ${CYAN}https://$NGROK_DOMAIN/api/webhooks/whatsapp/${NC}"
    echo -e "   Meta:      ${CYAN}https://$NGROK_DOMAIN/api/webhooks/meta/${NC}"
    echo ""
    echo -e "   Para encerrar: ${YELLOW}./start.sh stop${NC}"
    echo ""
    ;;
  stop)
    stop_all
    ;;
  restart)
    stop_all
    sleep 1
    exec "$0" start
    ;;
  status)
    echo ""
    for name in backend frontend; do
      pidfile="$LOG_DIR/$name.pid"
      if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        success "$name rodando (PID $(cat "$pidfile"))"
      else
        warn "$name parado"
      fi
    done
    echo ""
    ;;
  logs)
    echo -e "${CYAN}=== Backend ===${NC}"
    tail -20 "$LOG_DIR/backend.log" 2>/dev/null || echo "(sem log)"
    echo ""
    echo -e "${CYAN}=== Frontend ===${NC}"
    tail -20 "$LOG_DIR/frontend.log" 2>/dev/null || echo "(sem log)"
    ;;
  *)
    echo "Uso: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
