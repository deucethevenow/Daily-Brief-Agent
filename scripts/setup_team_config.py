"""One-time setup: seed GCS team config by matching Asana users to Slack users.

Usage:
    source venv/bin/activate
    python scripts/setup_team_config.py          # dry run (prints config)
    python scripts/setup_team_config.py --upload  # upload to GCS

Matches Asana workspace users to Slack workspace users by display name.
Generates monitored_users.json and optionally uploads to GCS.
"""
import json
import os
import sys

# Add parent dir to path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

import ssl
import certifi
import asana
from slack_sdk import WebClient
from config import Config
from utils.team_config import GCS_BUCKET, GCS_CONFIG_BLOB, save_config_to_gcs


def get_asana_users():
    """Fetch all users from the Asana workspace."""
    configuration = asana.Configuration()
    configuration.access_token = Config.ASANA_ACCESS_TOKEN
    api_client = asana.ApiClient(configuration)
    users_api = asana.UsersApi(api_client)

    users = list(users_api.get_users_for_workspace(
        Config.ASANA_WORKSPACE_GID,
        opts={'opt_fields': 'name,email'}
    ))

    return [{'name': u.get('name', ''), 'email': u.get('email', ''), 'gid': u.get('gid', '')} for u in users]


def get_slack_users():
    """Fetch all users from the Slack workspace."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    client = WebClient(token=Config.SLACK_BOT_TOKEN, ssl=ssl_context)

    result = client.users_list()
    users = []
    for member in result.get('members', []):
        if member.get('deleted') or member.get('is_bot') or member.get('id') == 'USLACKBOT':
            continue
        profile = member.get('profile', {})
        users.append({
            'slack_user_id': member['id'],
            'name': profile.get('real_name', ''),
            'display_name': profile.get('display_name', ''),
            'email': profile.get('email', ''),
        })

    return users


def match_users(asana_users, slack_users):
    """Match Asana users to Slack users by name or email."""
    # Build lookup maps
    slack_by_email = {u['email'].lower(): u for u in slack_users if u.get('email')}
    slack_by_name = {}
    for u in slack_users:
        slack_by_name[u['name'].lower()] = u
        if u.get('display_name'):
            slack_by_name[u['display_name'].lower()] = u

    matched = []

    for asana_user in asana_users:
        name = asana_user['name']
        email = asana_user.get('email', '').lower()

        # Try email match first (most reliable)
        slack_match = slack_by_email.get(email)

        # Fall back to name match
        if not slack_match:
            slack_match = slack_by_name.get(name.lower())

        if slack_match:
            matched.append({
                'name': name,
                'enabled': True,
                'slack_user_id': slack_match['slack_user_id'],
                'asana_gid': asana_user.get('gid', ''),
                'email': email or slack_match.get('email', ''),
            })
        else:
            # No Slack match — still add to config, just without Slack ID
            matched.append({
                'name': name,
                'enabled': True,
                'slack_user_id': None,
                'asana_gid': asana_user.get('gid', ''),
                'email': email,
            })

    return matched


def main():
    upload = '--upload' in sys.argv

    print("🔍 Fetching Asana workspace users...")
    asana_users = get_asana_users()
    print(f"   Found {len(asana_users)} Asana users")

    # Try to fetch Slack users for matching (requires users:read scope)
    slack_users = []
    try:
        print("🔍 Fetching Slack workspace users...")
        slack_users = get_slack_users()
        print(f"   Found {len(slack_users)} Slack users")
    except Exception as e:
        print(f"⚠️  Slack user fetch failed ({e})")
        print("   Continuing without Slack IDs — @mentions will use names instead")
        print("   To enable @mentions, add 'users:read' scope to the Slack bot")

    print("\n🔗 Matching users...")
    matched = match_users(asana_users, slack_users)

    print(f"\n✅ Found {len(matched)} Asana users:")
    with_slack = [u for u in matched if u.get('slack_user_id')]
    without_slack = [u for u in matched if not u.get('slack_user_id')]
    for u in sorted(matched, key=lambda x: x['name']):
        slack_id = u.get('slack_user_id') or 'no Slack ID'
        enabled = '✅' if u.get('enabled') else '⬜'
        print(f"   {enabled} {u['name']} → Slack: {slack_id}")

    if without_slack:
        print(f"\n⚠️  {len(without_slack)} users have no Slack ID (will use name in #team messages)")

    config = {'monitored_users': matched}

    # Write locally for reference
    local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'monitored_users.json')
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"\n💾 Saved local copy: {local_path}")

    if upload:
        print(f"\n☁️  Uploading to gs://{GCS_BUCKET}/{GCS_CONFIG_BLOB}...")
        if save_config_to_gcs(config):
            print("✅ Uploaded successfully!")
        else:
            print("❌ Upload failed — check logs")
            sys.exit(1)
    else:
        print(f"\n📋 Dry run — to upload to GCS, run:")
        print(f"   python scripts/setup_team_config.py --upload")

    print(f"\n📊 Summary: {len(matched)} users ready for monitoring")


if __name__ == '__main__':
    main()
