#!/usr/bin/env python3
"""Send a test message to Slack."""
import ssl
import certifi
from slack_sdk import WebClient
from config import Config

# Fix SSL for macOS
ssl_context = ssl.create_default_context(cafile=certifi.where())

# Create Slack client
client = WebClient(token=Config.SLACK_BOT_TOKEN, ssl=ssl_context)

# Send test message
print(f"Sending test message to channel: {Config.SLACK_CHANNEL_ID}")

try:
    response = client.chat_postMessage(
        channel=Config.SLACK_CHANNEL_ID,
        text="🎉 Test message from Daily Brief Agent!",
        blocks=[
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✅ Daily Brief Agent Test",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This is a test message to confirm Slack integration is working!\n\n*Status*: All systems operational ✓"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "If you can see this, Slack integration is working perfectly!"
                    }
                ]
            }
        ]
    )

    print("✓ Message sent successfully!")
    print(f"  Channel: {response['channel']}")
    print(f"  Timestamp: {response['ts']}")
    print(f"\nCheck your Slack channel now!")

except Exception as e:
    print(f"✗ Failed to send message: {e}")
