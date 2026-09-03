#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/.soc-server.pid"
LOG_FILE="$SCRIPT_DIR/server.log"
APP="$SCRIPT_DIR/backend/app.py"

start_server() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Server already running (PID $(cat "$PID_FILE"))"
        return 0
    fi
    echo "Starting SOC Threat Dashboard..."
    nohup env PYTHONUNBUFFERED=1 python3 "$APP" >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    sleep 1
    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Server started (PID $(cat "$PID_FILE")), log: $LOG_FILE"
    else
        echo "Failed to start. Check $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "Stopping server (PID $PID)..."
            kill "$PID" 2>/dev/null || true
            sleep 0.5
        fi
        rm -f "$PID_FILE"
    fi
    pkill -f "backend/app.py" 2>/dev/null || true
    echo "Server stopped."
}

status_server() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Server running (PID $(cat "$PID_FILE"))"
    else
        echo "Server not running"
        rm -f "$PID_FILE" 2>/dev/null
    fi
}

case "${1:-}" in
    start)   start_server ;;
    stop)    stop_server ;;
    restart) stop_server; sleep 1; start_server ;;
    status)  status_server ;;
    log)     tail -f "$LOG_FILE" 2>/dev/null || echo "No log file yet." ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|log}"
        exit 1
        ;;
esac
