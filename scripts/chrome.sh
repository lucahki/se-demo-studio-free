#!/bin/bash
# Start (or confirm) this job's dedicated Chrome with its own profile and remote debugging, then sign in there
# yourself. Claude never types, reads, or stores passwords, codes, cookies, or tokens.
# usage: scripts/chrome.sh <job-slug> [url]      scripts/chrome.sh <job-slug> --stop
cd "$(dirname "$0")/.."
. scripts/platform.sh
SLUG=${1:?usage: scripts/chrome.sh <job-slug> [url|--stop]}; DIR=jobs/$SLUG
[ -f "$DIR/job.json" ] || { echo "No job $SLUG"; exit 1; }
[ -n "$PYTHON" ] || { echo "Python 3 is missing: run scripts/setup.sh"; exit 1; }
PORT=$($PYTHON -c "import json; print(json.load(open('$DIR/job.json'))['chrome_port'])")
URL=${2:-$($PYTHON -c "import json; print(json.load(open('$DIR/job.json'))['app_url'])")}
if [ "${2:-}" = "--stop" ]; then
  if [ $PLATFORM = windows ]; then
    # the Chrome whose command line has this job's port; asked to close, then forced if it is still open after 5 s
    PIDS=$(powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | Where-Object { \$_.CommandLine -like '*--remote-debugging-port=$PORT *' } | ForEach-Object { \$_.ProcessId }" | tr -d '\r')
    [ -n "$PIDS" ] || { echo "No Chrome on port $PORT"; exit 0; }
    for p in $PIDS; do taskkill //PID $p >/dev/null 2>&1; done
    for i in $(seq 1 10); do curl -s -m 1 "http://127.0.0.1:$PORT/json/version" >/dev/null || break; sleep 0.5; done
    for p in $PIDS; do taskkill //F //PID $p >/dev/null 2>&1; done
    echo "Stopped Chrome on port $PORT"; exit 0
  fi
  pkill -f -- "--remote-debugging-port=$PORT" && echo "Stopped Chrome on port $PORT" || echo "No Chrome on port $PORT"; exit 0
fi
if curl -s -m 3 "http://127.0.0.1:$PORT/json/version" >/dev/null; then echo "Chrome already running on port $PORT"; exit 0; fi
[ -n "$CHROME" ] || { echo "Google Chrome is not installed: https://www.google.com/chrome"; exit 1; }
"$CHROME" --user-data-dir="$(winpath "$PWD/$DIR/.chrome-profile")" \
  --remote-debugging-port=$PORT --no-first-run --no-default-browser-check --window-size=1920,1200 \
  --hide-crash-restore-bubble --disable-backgrounding-occluded-windows --disable-renderer-backgrounding \
  --disable-background-timer-throttling "$URL" >/dev/null 2>&1 &
for i in $(seq 1 20); do curl -s -m 2 "http://127.0.0.1:$PORT/json/version" >/dev/null && { echo "Chrome started on port $PORT. Sign in to the demo in that window."; exit 0; }; sleep 1; done
echo "Chrome did not answer on port $PORT"; exit 1
