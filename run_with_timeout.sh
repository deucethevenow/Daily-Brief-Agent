#!/bin/bash
#
# Timeout wrapper for daily brief
# Kills the process if it runs longer than 10 minutes (wall-clock time)
# Sends Slack notifications for bash-level failures
#

TIMEOUT=900  # 15 minutes in seconds (matches Cloud Run job timeout)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cd "$SCRIPT_DIR"

# Load environment variables for Slack notifications
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | grep -E '^(SLACK_BOT_TOKEN|SLACK_CHANNEL_ID)=' | xargs)
fi

# Function to send Slack notification for script-level failures
send_slack_error() {
    local error_title="$1"
    local error_message="$2"
    local exit_code="$3"

    # Only send if we have Slack credentials
    if [ -z "$SLACK_BOT_TOKEN" ] || [ -z "$SLACK_CHANNEL_ID" ]; then
        echo "ERROR: Cannot send Slack notification - missing credentials" >&2
        return 1
    fi

    # Build JSON payload
    local payload=$(cat <<EOF
{
    "channel": "$SLACK_CHANNEL_ID",
    "text": "⚠️ Daily Brief Script Failed",
    "blocks": [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "⚠️ Daily Brief Script Error"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*${error_title}*\n\n\`\`\`${error_message}\`\`\`"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": "*Exit Code:*\n${exit_code}"
                },
                {
                    "type": "mrkdwn",
                    "text": "*Time:*\n$(date '+%Y-%m-%d %H:%M:%S %Z')"
                }
            ]
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Check \`logs/launchd.err.log\` for more details."
                }
            ]
        }
    ]
}
EOF
)

    # Send to Slack
    curl -s -X POST \
        -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload" \
        https://slack.com/api/chat.postMessage > /dev/null 2>&1
}

# Check if gtimeout is available
if ! command -v gtimeout &> /dev/null; then
    ERROR_MSG="Command 'gtimeout' not found in PATH.\n\nPATH: $PATH\n\nThe daily brief cannot run without the timeout utility.\nInstall with: brew install coreutils"
    echo "ERROR: $ERROR_MSG" >&2
    send_slack_error "Command Not Found: gtimeout" "$ERROR_MSG" "127"
    exit 127
fi

# Check if Python venv exists
if [ ! -f "$SCRIPT_DIR/venv/bin/python" ]; then
    ERROR_MSG="Python virtual environment not found at:\n$SCRIPT_DIR/venv/bin/python\n\nRun setup: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    echo "ERROR: $ERROR_MSG" >&2
    send_slack_error "Python Virtual Environment Missing" "$ERROR_MSG" "126"
    exit 126
fi

# Wait for network to be ready (important when Mac wakes from sleep)
echo "Checking network connectivity..."
MAX_NETWORK_WAIT=60  # Wait up to 60 seconds for network
NETWORK_CHECK_INTERVAL=5
ELAPSED=0

while [ $ELAPSED -lt $MAX_NETWORK_WAIT ]; do
    # Try to resolve a DNS name
    if host api.airtable.com > /dev/null 2>&1; then
        echo "Network ready after ${ELAPSED}s"
        break
    fi
    echo "Waiting for network... (${ELAPSED}s elapsed)"
    sleep $NETWORK_CHECK_INTERVAL
    ELAPSED=$((ELAPSED + NETWORK_CHECK_INTERVAL))
done

# Final network check
if ! host api.airtable.com > /dev/null 2>&1; then
    ERROR_MSG="Network not available after ${MAX_NETWORK_WAIT} seconds.\n\nCould not resolve api.airtable.com\n\nThis typically happens when the Mac is waking from sleep and network services aren't ready."
    echo "ERROR: $ERROR_MSG" >&2
    send_slack_error "Network Unavailable" "$ERROR_MSG" "125"
    exit 125
fi

# Run coordinator.py with timeout (using gtimeout from coreutils)
gtimeout $TIMEOUT "$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/coordinator.py"

EXIT_CODE=$?

# Exit code 124 means timeout was reached
if [ $EXIT_CODE -eq 124 ]; then
    ERROR_MSG="Daily brief exceeded ${TIMEOUT} second timeout and was killed.\n\nThis may indicate:\n- Slow API responses\n- Too many tasks to process\n- Network issues\n\nConsider increasing TIMEOUT or investigating performance."
    echo "ERROR: $ERROR_MSG" >&2
    send_slack_error "Script Timeout Exceeded" "$ERROR_MSG" "124"
    exit 1
fi

# Non-zero exit from Python script (but not timeout)
if [ $EXIT_CODE -ne 0 ]; then
    ERROR_MSG="coordinator.py exited with non-zero status.\n\nThis indicates a Python-level error.\nThe Python script should have sent its own detailed error notification.\n\nIf you didn't receive a Python error notification, check logs/daily_brief_*.log"
    echo "ERROR: Python script failed with exit code $EXIT_CODE" >&2
    send_slack_error "Python Script Failed" "$ERROR_MSG" "$EXIT_CODE"
fi

exit $EXIT_CODE
