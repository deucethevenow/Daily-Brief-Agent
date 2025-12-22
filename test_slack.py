#!/usr/bin/env python3
"""Test Slack connection and message sending."""
import sys
import os
from integrations.slack_client import SlackClient
from utils import setup_logger

logger = setup_logger(__name__)

def test_slack():
    """Test Slack connection with detailed response logging."""
    print("\n🔍 Testing Slack Connection...\n")

    try:
        # Initialize client
        slack = SlackClient()
        print(f"✓ Slack client initialized")
        print(f"  Channel ID: {slack.channel_id}")
        print(f"  Bot Token: {slack.client.token[:20]}...{slack.client.token[-10:]}\n")

        # Send a test message
        print("📤 Sending test message...")
        response = slack.send_message(
            text="🧪 Test Message - Daily Brief Diagnostics",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*🧪 Slack Connection Test*\n\nThis is a diagnostic test message. If you see this, Slack posting is working correctly."
                    }
                }
            ]
        )

        # Print detailed response
        print("\n✅ Message sent successfully!")
        print(f"\nAPI Response Details:")
        print(f"  - OK: {response.get('ok')}")
        print(f"  - Channel: {response.get('channel')}")
        print(f"  - Timestamp: {response.get('ts')}")
        print(f"  - Message: {response.get('message', {}).get('text', 'N/A')}")

        if response.get('warning'):
            print(f"  ⚠️  Warning: {response.get('warning')}")

        print(f"\n🔗 Full Response:")
        print(f"  {response}")

        return True

    except Exception as e:
        print(f"\n❌ Error sending Slack message:")
        print(f"  Type: {type(e).__name__}")
        print(f"  Message: {str(e)}")

        if hasattr(e, 'response'):
            print(f"  Response Error: {e.response.get('error', 'Unknown')}")
            print(f"  Full Response: {e.response}")

        logger.error(f"Slack test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_slack()
    sys.exit(0 if success else 1)
