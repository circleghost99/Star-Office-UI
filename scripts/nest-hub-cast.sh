#!/bin/bash
# Star Office → Nest Hub 自動投放腳本
# 每 5 分鐘檢查一次，如果 Nest Hub 沒在顯示 Star Office 就重新投放

CATT="/Users/circleghost/.openclaw/workspace/Star-Office-UI/.venv/bin/catt"
DEVICE="工作房 Display"
OFFICE_URL="http://192.168.31.110:19000/?nest"
LOG="/Users/circleghost/.openclaw/logs/nest-hub-cast.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

# Check if backend is up
if ! curl -s --max-time 3 http://127.0.0.1:19000/health > /dev/null 2>&1; then
    log "Backend not responding, skipping cast"
    exit 0
fi

# Check Nest Hub status
STATUS=$("$CATT" -d "$DEVICE" status 2>&1)

if echo "$STATUS" | grep -q "Casting"; then
    log "Already casting, skip"
    exit 0
fi

# Cast to Nest Hub
log "Casting to $DEVICE: $OFFICE_URL"
"$CATT" -d "$DEVICE" cast_site "$OFFICE_URL" >> "$LOG" 2>&1

if [ $? -eq 0 ]; then
    log "Cast successful"
else
    log "Cast failed"
fi
