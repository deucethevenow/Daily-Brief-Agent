#!/usr/bin/env python3
"""Interactive .env validation and helper script."""
import os
import sys
from pathlib import Path


def print_header(text):
    """Print a styled header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_status(check, message):
    """Print a status message with checkmark or X."""
    icon = "✓" if check else "✗"
    color = "\033[92m" if check else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{icon}{reset} {message}")


def check_env_file():
    """Check if .env file exists."""
    env_path = Path(__file__).parent / '.env'
    return env_path.exists()


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent / '.env'
    env_vars = {}

    if not env_path.exists():
        return env_vars

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def validate_anthropic(api_key):
    """Validate Anthropic API key format."""
    if not api_key:
        return False, "Missing API key"
    if not api_key.startswith('sk-ant-'):
        return False, "Should start with 'sk-ant-'"
    if len(api_key) < 20:
        return False, "Key seems too short"
    return True, "Format looks correct"


def validate_airtable_token(token):
    """Validate Airtable token format."""
    if not token:
        return False, "Missing token"
    if not token.startswith('pat'):
        return False, "Should start with 'pat'"
    if len(token) < 20:
        return False, "Token seems too short"
    return True, "Format looks correct"


def validate_airtable_base(base_id):
    """Validate Airtable Base ID format."""
    if not base_id:
        return False, "Missing Base ID"
    if not base_id.startswith('app'):
        return False, "Should start with 'app'"
    if len(base_id) != 17:
        return False, f"Should be 17 characters (got {len(base_id)})"
    return True, "Format looks correct"


def validate_asana_token(token):
    """Validate Asana token format."""
    if not token:
        return False, "Missing token"
    if not (token.startswith('1/') or token.startswith('2/')):
        return False, "Should start with '1/' or '2/'"
    if ':' not in token:
        return False, "Should contain ':'"
    if len(token) < 30:
        return False, "Token seems too short"
    return True, "Format looks correct"


def validate_slack_token(token):
    """Validate Slack bot token format."""
    if not token:
        return False, "Missing token"
    if not token.startswith('xoxb-'):
        return False, "Should start with 'xoxb-'"
    if len(token) < 40:
        return False, "Token seems too short"
    return True, "Format looks correct"


def validate_slack_channel(channel_id):
    """Validate Slack channel/user ID format."""
    if not channel_id:
        return False, "Missing Channel/User ID"
    if not (channel_id.startswith('C') or channel_id.startswith('U')):
        return False, "Should start with 'C' (channel) or 'U' (user)"
    if len(channel_id) != 11:
        return False, f"Should be 11 characters (got {len(channel_id)})"
    return True, "Format looks correct"


def main():
    """Main validation flow."""
    print_header("Daily Brief Agent - Environment Validation")

    # Check if .env exists
    if not check_env_file():
        print_status(False, ".env file not found")
        print("\n📝 Create your .env file:")
        print("   cp .env.template .env")
        print("   nano .env")
        print("\nThen run this script again to validate.")
        return False

    print_status(True, ".env file found")

    # Load environment
    env = load_env()

    # Required variables
    required = {
        'ANTHROPIC_API_KEY': ('Anthropic Claude API', validate_anthropic),
        'AIRTABLE_API_KEY': ('Airtable Token', validate_airtable_token),
        'AIRTABLE_BASE_ID': ('Airtable Base ID', validate_airtable_base),
        'AIRTABLE_TABLE_NAME': ('Airtable Table Name', None),
        'ASANA_ACCESS_TOKEN': ('Asana Token', validate_asana_token),
        'ASANA_WORKSPACE_GID': ('Asana Workspace GID', None),
        'SLACK_BOT_TOKEN': ('Slack Bot Token', validate_slack_token),
        'SLACK_CHANNEL_ID': ('Slack Channel/User ID', validate_slack_channel),
    }

    print_header("Checking Required Configuration")

    all_valid = True
    warnings = []

    for key, (name, validator) in required.items():
        value = env.get(key, '')

        if not value:
            print_status(False, f"{name}: Not set")
            all_valid = False
            continue

        if validator:
            is_valid, message = validator(value)
            if is_valid:
                print_status(True, f"{name}: {message}")
            else:
                print_status(False, f"{name}: {message}")
                all_valid = False
        else:
            print_status(True, f"{name}: Set to '{value}'")

    # Optional but recommended
    print_header("Checking Optional Configuration")

    your_name = env.get('YOUR_NAME', '')
    if your_name:
        print_status(True, f"Your Name: '{your_name}'")
    else:
        print_status(False, "Your Name: Not set (action items won't be filtered)")
        warnings.append("Consider setting YOUR_NAME to filter action items")

    timezone = env.get('TIMEZONE', 'America/Denver')
    print_status(True, f"Timezone: {timezone}")

    auto_create = env.get('AUTO_CREATE_TASKS', 'false')
    if auto_create.lower() == 'true':
        print_status(True, "Auto-create tasks: ENABLED")
        warnings.append("Consider starting with AUTO_CREATE_TASKS=false to verify quality first")
    else:
        print_status(True, "Auto-create tasks: Disabled (suggestion mode)")

    # Summary
    print_header("Validation Summary")

    if all_valid:
        print_status(True, "All required configuration looks good!")
        print("\n📝 Next steps:")
        print("   1. Test connections: python coordinator.py")
        print("   2. Start scheduler: python scheduler.py")
    else:
        print_status(False, "Some configuration issues found")
        print("\n📝 Next steps:")
        print("   1. Fix the issues above")
        print("   2. See SETUP_GUIDE.md for detailed instructions")
        print("   3. Run this script again to re-validate")

    if warnings:
        print("\n⚠️  Warnings:")
        for warning in warnings:
            print(f"   • {warning}")

    print("\n" + "=" * 60 + "\n")

    return all_valid


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nValidation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
