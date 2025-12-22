#!/usr/bin/env python3
"""Quick connection test script."""
import sys
from config import Config

def test_claude():
    """Test Claude API."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )
        print("✓ Claude API: Connected")
        return True
    except Exception as e:
        print(f"✗ Claude API: {e}")
        return False

def test_airtable():
    """Test Airtable."""
    try:
        from integrations import AirtableClient
        client = AirtableClient()
        meetings = client.get_today_meetings()
        print(f"✓ Airtable: Connected ({len(meetings)} meetings today)")
        return True
    except Exception as e:
        print(f"✗ Airtable: {e}")
        return False

def test_slack():
    """Test Slack."""
    try:
        import ssl
        import certifi
        from slack_sdk import WebClient
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        client = WebClient(token=Config.SLACK_BOT_TOKEN, ssl=ssl_context)
        response = client.auth_test()
        print(f"✓ Slack: Connected (bot: {response['user']})")
        return True
    except Exception as e:
        print(f"✗ Slack: {e}")
        return False

def test_asana():
    """Test Asana."""
    try:
        import asana
        configuration = asana.Configuration()
        configuration.access_token = Config.ASANA_ACCESS_TOKEN
        api_client = asana.ApiClient(configuration)
        projects_api = asana.ProjectsApi(api_client)

        # Just get first page of projects
        projects = projects_api.get_projects_for_workspace(
            Config.ASANA_WORKSPACE_GID,
            opts={'limit': 1}
        )
        print(f"✓ Asana: Connected")
        return True
    except Exception as e:
        print(f"✗ Asana: {e}")
        return False

if __name__ == "__main__":
    print("Testing API Connections...")
    print("-" * 40)

    Config.validate()

    results = {
        'Claude': test_claude(),
        'Airtable': test_airtable(),
        'Slack': test_slack(),
        'Asana': test_asana(),
    }

    print("-" * 40)
    passed = sum(results.values())
    total = len(results)
    print(f"\nResults: {passed}/{total} passed")

    if passed == total:
        print("\n🎉 All connections successful!")
        print("Ready to run: python coordinator.py")
        sys.exit(0)
    else:
        print("\n⚠️  Some connections failed. See errors above.")
        sys.exit(1)
