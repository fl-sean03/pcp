#!/bin/bash
# PCP Scheduled Task Runner
# Runs a scheduler task and sends output to Discord

TASK="$1"
WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
MAX_LENGTH=1900  # Discord message limit is 2000

if [ -z "$TASK" ]; then
    echo "Usage: $0 <task>"
    echo "Tasks: brief, reminder, pattern, sync, escalate, email, eod, weekly"
    exit 1
fi

# Run the task directly (not through scheduler.py) to get clean output
# Use 2>/dev/null to suppress warnings, or filter them out
case "$TASK" in
    brief)
        OUTPUT=$(docker exec pcp-agent python3 /workspace/scripts/brief.py --daily 2>/dev/null)
        ;;
    eod)
        OUTPUT=$(docker exec pcp-agent python3 /workspace/scripts/brief.py --eod 2>/dev/null)
        ;;
    weekly)
        OUTPUT=$(docker exec pcp-agent python3 /workspace/scripts/brief.py --weekly 2>/dev/null)
        ;;
    *)
        # For other tasks, use scheduler
        OUTPUT=$(docker exec pcp-agent python3 /workspace/scripts/scheduler.py --run "$TASK" 2>/dev/null)
        ;;
esac

# Skip sending if output is empty or just whitespace
if [ -z "$(echo "$OUTPUT" | tr -d '[:space:]')" ]; then
    echo "No output for task: $TASK"
    exit 0
fi

# Truncate if too long
if [ ${#OUTPUT} -gt $MAX_LENGTH ]; then
    OUTPUT="${OUTPUT:0:$MAX_LENGTH}...

(truncated)"
fi

# Format based on task type (no title prefix for briefs - they're self-explanatory)
case "$TASK" in
    brief|eod|weekly)
        # Brief already has greeting, no need for title
        FINAL_OUTPUT="$OUTPUT"
        ;;
    *)
        FINAL_OUTPUT="**PCP: $TASK**

$OUTPUT"
        ;;
esac

# Only send to Discord for certain tasks (briefs, not routine checks)
SEND_TO_DISCORD=false
case "$TASK" in
    brief|eod|weekly)
        SEND_TO_DISCORD=true
        ;;
esac

if [ "$SEND_TO_DISCORD" = true ] && [ -n "$WEBHOOK_URL" ]; then
    # Send to Discord using jq with raw input to preserve newlines
    PAYLOAD=$(jq -Rs '{content: .}' <<< "$FINAL_OUTPUT")
    curl -s -H "Content-Type: application/json" -d "$PAYLOAD" "$WEBHOOK_URL" > /dev/null
    echo "Sent $TASK to Discord"
elif [ "$SEND_TO_DISCORD" = true ]; then
    echo "DISCORD_WEBHOOK_URL not set, skipping Discord notification"
else
    echo "Task $TASK completed (not sent to Discord)"
fi
