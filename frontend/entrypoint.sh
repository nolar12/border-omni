#!/bin/sh
set -e

cat > /usr/share/nginx/html/env-config.js <<EOF
window._env = {
  API_URL: "${API_URL}",
  APP_ENV: "${APP_ENV}"
};
EOF

exec nginx -g "daemon off;"
