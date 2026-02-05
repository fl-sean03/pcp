#!/bin/bash
# PCP Scheduled Brief - Generates and sends briefs on schedule
#
# Usage:
#   ./scheduled_brief.sh daily    # Morning daily brief
#   ./scheduled_brief.sh weekly   # Weekly summary
#   ./scheduled_brief.sh eod      # End-of-day digest
#
# Cron examples:
#   0 8 * * * /workspace/scripts/scheduled_brief.sh daily
#   0 9 * * 0 /workspace/scripts/scheduled_brief.sh weekly
#   0 18 * * * /workspace/scripts/scheduled_brief.sh eod

set -e

SCRIPTS_DIR="${PCP_DIR:-/workspace}/scripts"
LOG_DIR="${PCP_DIR:-/workspace}/.agent"
LOG_FILE="$LOG_DIR/scheduled_brief.log"
CONFIG_FILE="${PCP_DIR:-/workspace}/.reminder_config.json"

mkdir -p "$LOG_DIR"

BRIEF_TYPE="${1:-daily}"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

log() {
    echo "[$TIMESTAMP] $1" >> "$LOG_FILE"
}

log "Starting $BRIEF_TYPE brief generation"

# Generate the brief
case "$BRIEF_TYPE" in
    daily)
        BRIEF=$(python3 "$SCRIPTS_DIR/brief.py" --daily 2>&1)
        ;;
    weekly)
        BRIEF=$(python3 "$SCRIPTS_DIR/brief.py" --weekly 2>&1)
        ;;
    eod)
        BRIEF=$(python3 "$SCRIPTS_DIR/brief.py" --eod 2>&1)
        ;;
    *)
        log "Unknown brief type: $BRIEF_TYPE"
        echo "Usage: $0 {daily|weekly|eod}"
        exit 1
        ;;
esac

if [ $? -ne 0 ]; then
    log "Error generating brief: $BRIEF"
    exit 1
fi

log "Brief generated successfully"

# Try to send via Discord webhook if configured
if [ -f "$CONFIG_FILE" ]; then
    WEBHOOK_URL=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('discord_webhook', ''))" 2>/dev/null)

    if [ -n "$WEBHOOK_URL" ]; then
        # Discord has a 2000 char limit per message, split if needed
        # For now, truncate to fit
        BRIEF_TRUNCATED=$(echo "$BRIEF" | head -c 1900)

        # Send via webhook
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Content-Type: application/json" \
            -d "{\"content\": \"$BRIEF_TRUNCATED\"}" \
            "$WEBHOOK_URL")

        if [ "$RESPONSE" = "204" ]; then
            log "Brief sent to Discord successfully"
        else
            log "Discord webhook returned: $RESPONSE"
        fi
    else
        log "Discord webhook not configured, outputting to stdout"
        echo "$BRIEF"
    fi
else
    log "No config file found, outputting to stdout"
    echo "$BRIEF"
fi

# Also save the brief to a file for reference
BRIEF_FILE="$LOG_DIR/last_${BRIEF_TYPE}_brief.md"
echo "$BRIEF" > "$BRIEF_FILE"
log "Brief saved to $BRIEF_FILE"

log "Completed $BRIEF_TYPE brief"
