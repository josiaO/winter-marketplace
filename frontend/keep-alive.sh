#!/bin/bash
while true; do
  cd /home/z/my-project
  echo "Starting dev server at $(date)" >> /home/z/my-project/keep-alive.log
  bun run dev >> /home/z/my-project/dev.log 2>&1
  echo "Dev server died at $(date), restarting in 3s..." >> /home/z/my-project/keep-alive.log
  sleep 3
done
