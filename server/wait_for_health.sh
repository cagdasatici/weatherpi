#!/usr/bin/env bash
set -euo pipefail

# wait_for_health.sh
# Wait until the proxy /api/health returns HTTP 200, or timeout.
# Usage: wait_for_health.sh [URL] [RETRIES] [SLEEP_SECONDS]
# Defaults: URL=http://127.0.0.1:8000/api/health, RETRIES=30, SLEEP=2

URL=${1:-http://127.0.0.1:8000/api/health}
RETRIES=${2:-30}
SLEEP=${3:-2}

count=0
echo "Waiting for health at $URL (retries: $RETRIES, sleep: $SLEEP)"
while [ $count -lt $RETRIES ]; do
  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "$URL" || echo 000)
  if [ "$status" = "200" ]; then
    echo "Service healthy"
    exit 0
  fi
  count=$((count+1))
  echo "  attempt $count/$RETRIES -> $status"
  sleep $SLEEP
done

echo "Health check failed after $RETRIES attempts"
exit 1
