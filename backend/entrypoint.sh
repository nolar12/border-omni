#!/bin/bash
set -e

python - <<'PYEOF'
import time, pymysql, os, sys
host     = os.environ.get("DB_HOST", "localhost")
port     = int(os.environ.get("DB_PORT", 3306))
user     = os.environ.get("DB_USER", "")
password = os.environ.get("DB_PASSWORD", "")
db       = os.environ.get("DB_NAME", "")
for attempt in range(30):
    try:
        conn = pymysql.connect(
            host=host, port=port, user=user,
            password=password, db=db, connect_timeout=3
        )
        conn.close()
        print("[entrypoint] MySQL pronto.")
        sys.exit(0)
    except Exception as e:
        print(f"[entrypoint] Tentativa {attempt+1}/30: {e}")
        time.sleep(2)
sys.exit(1)
PYEOF

echo "[entrypoint] ALLOWED_HOSTS: $ALLOWED_HOSTS"
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
exec gunicorn config.wsgi:application --config gunicorn.conf.py
