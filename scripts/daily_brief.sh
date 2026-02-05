#!/bin/bash
# PCP Daily Brief - Generates and sends daily brief
# This script is called by cron to generate a daily summary

set -e

WORKSPACE="/workspace"
SCRIPTS_DIR="$WORKSPACE/scripts"
LOG_DIR="$WORKSPACE/.agent"
LOG_FILE="$LOG_DIR/brief.log"

mkdir -p "$LOG_DIR"

# Generate timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
echo "=== Daily Brief $TIMESTAMP ===" >> "$LOG_FILE"

# Generate the brief using the v2 brief engine
echo "[$TIMESTAMP] Generating daily brief..." >> "$LOG_FILE"
BRIEF=$(python3 "$SCRIPTS_DIR/brief.py" 2>&1)

if [ $? -eq 0 ]; then
    echo "[$TIMESTAMP] Brief generated successfully" >> "$LOG_FILE"

    # Also run pattern analysis
    echo "[$TIMESTAMP] Running pattern analysis..." >> "$LOG_FILE"
    PATTERNS=$(python3 "$SCRIPTS_DIR/patterns.py" 2>&1)

    # Check and escalate reminders
    echo "[$TIMESTAMP] Checking reminders..." >> "$LOG_FILE"
    python3 "$SCRIPTS_DIR/reminders.py" --escalate >> "$LOG_FILE" 2>&1
    python3 "$SCRIPTS_DIR/reminders.py" --check >> "$LOG_FILE" 2>&1

    echo "[$TIMESTAMP] Daily brief complete" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    # Output the brief (for Discord bot to capture)
    echo "$BRIEF"
    echo ""
    echo "---"
    echo ""
    echo "$PATTERNS"
else
    echo "[$TIMESTAMP] Error generating brief: $BRIEF" >> "$LOG_FILE"
    exit 1
fi

echo "=== Brief Complete ===" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
