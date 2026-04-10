#!/bin/bash
cd /home/z/my-project
while true; do
  rm -rf .next
  echo "=== Starting dev server at $(date) ==="
  npx next dev -p 3000 2>&1
  echo "=== Server exited at $(date), restarting in 2s ==="
  sleep 2
done
