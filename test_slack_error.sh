#!/bin/bash
#
# Test script to verify Slack error notifications work
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load the send_slack_error function from run_with_timeout.sh
source <(sed -n '/^send_slack_error()/,/^}/p' "$SCRIPT_DIR/run_with_timeout.sh")

# Load environment variables
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | grep -E '^(SLACK_BOT_TOKEN|SLACK_CHANNEL_ID)=' | xargs)
fi

# Test the Slack notification
echo "Testing Slack error notification..."
send_slack_error \
    "Test Error Notification" \
    "This is a test of the bash-level error notification system.\n\nIf you see this message in Slack, the error handling is working correctly!" \
    "0"

if [ $? -eq 0 ]; then
    echo "✓ Test notification sent successfully!"
    echo "Check your Slack channel: $SLACK_CHANNEL_ID"
else
    echo "✗ Failed to send test notification"
    exit 1
fi
