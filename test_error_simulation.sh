#!/bin/bash
#
# Simulate the original PATH error to test notifications
#

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "============================================"
echo "Simulating Original Error Scenario"
echo "============================================"
echo ""
echo "This will test what would happen if gtimeout"
echo "wasn't in the PATH (the original bug)."
echo ""

# Temporarily remove /opt/homebrew/bin from PATH to simulate the error
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "Modified PATH (simulating LaunchAgent environment):"
echo "$PATH"
echo ""

# Now try to run the daily brief with the broken PATH
echo "Running run_with_timeout.sh with broken PATH..."
echo "============================================"
echo ""

# Execute the script
"$SCRIPT_DIR/run_with_timeout.sh"

EXIT_CODE=$?

echo ""
echo "============================================"
echo "Script exited with code: $EXIT_CODE"
echo "============================================"
echo ""
echo "Check your Slack channel for the error notification!"
