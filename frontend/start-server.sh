#!/bin/bash
# Simple process monitor for Next.js dev server
cd /home/z/my-project

while true; do
  # Check if port 3000 is listening
  if ! ss -tlnp 2>/dev/null | grep -q ":3000 "; then
    echo "[$(date)] Server not running, starting..."
    rm -f dev.log
    npx next dev --port 3000 >> /home/z/my-project/dev.log 2>&1 &
    sleep 12
  fi
  sleep 5
done
