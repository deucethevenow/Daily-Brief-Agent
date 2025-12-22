#!/usr/bin/env python3
"""Setup script to help configure the Daily Brief Agent."""
import os
import sys
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.8 or higher."""
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✓ Python version: {sys.version.split()[0]}")
    return True


def check_virtual_env():
    """Check if running in a virtual environment."""
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    if not in_venv:
        print("⚠️  Warning: Not running in a virtual environment")
        print("   Recommendation: Create and activate a venv first")
        response = input("   Continue anyway? (y/n): ")
        return response.lower() == 'y'
    print("✓ Running in virtual environment")
    return True


def create_env_file():
    """Create .env file from .env.example if it doesn't exist."""
    env_path = Path(__file__).parent / '.env'
    example_path = Path(__file__).parent / '.env.example'

    if env_path.exists():
        print("⚠️  .env file already exists")
        response = input("   Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("   Keeping existing .env file")
            return True

    if not example_path.exists():
        print("❌ Error: .env.example not found")
        return False

    # Copy .env.example to .env
    with open(example_path, 'r') as src:
        content = src.read()

    with open(env_path, 'w') as dst:
        dst.write(content)

    print("✓ Created .env file from template")
    return True


def prompt_for_api_keys():
    """Guide user through entering API keys."""
    print("\n" + "="*60)
    print("API Configuration")
    print("="*60)
    print("\nYou'll need to provide API keys for the following services:")
    print("1. Anthropic Claude API")
    print("2. Airtable")
    print("3. Asana")
    print("4. Slack")
    print("\nWould you like to enter them now?")

    response = input("Configure API keys? (y/n): ")
    if response.lower() != 'y':
        print("\n⚠️  Remember to edit .env file manually before running!")
        return True

    env_path = Path(__file__).parent / '.env'
    env_vars = {}

    # Read existing .env
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value

    # Anthropic
    print("\n1. Anthropic Claude API Key")
    print("   Get from: https://console.anthropic.com/")
    api_key = input("   Enter API key: ").strip()
    if api_key:
        env_vars['ANTHROPIC_API_KEY'] = api_key

    # Airtable
    print("\n2. Airtable Configuration")
    print("   Get token from: https://airtable.com/create/tokens")
    airtable_key = input("   Enter API key: ").strip()
    base_id = input("   Enter Base ID (e.g., appXXXXXXXXXXXXXX): ").strip()
    table_name = input("   Enter Table Name (e.g., Meetings): ").strip()
    if airtable_key:
        env_vars['AIRTABLE_API_KEY'] = airtable_key
    if base_id:
        env_vars['AIRTABLE_BASE_ID'] = base_id
    if table_name:
        env_vars['AIRTABLE_TABLE_NAME'] = table_name

    # Asana
    print("\n3. Asana Configuration")
    print("   Get token from: https://app.asana.com/0/my-apps")
    asana_token = input("   Enter Access Token: ").strip()
    workspace_gid = input("   Enter Workspace GID: ").strip()
    if asana_token:
        env_vars['ASANA_ACCESS_TOKEN'] = asana_token
    if workspace_gid:
        env_vars['ASANA_WORKSPACE_GID'] = workspace_gid

    # Slack
    print("\n4. Slack Configuration")
    print("   Create app at: https://api.slack.com/apps")
    slack_token = input("   Enter Bot Token (xoxb-...): ").strip()
    channel_id = input("   Enter Channel ID: ").strip()
    if slack_token:
        env_vars['SLACK_BOT_TOKEN'] = slack_token
    if channel_id:
        env_vars['SLACK_CHANNEL_ID'] = channel_id

    # Write back to .env
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    print("\n✓ Configuration saved to .env")
    return True


def install_dependencies():
    """Install Python dependencies."""
    print("\n" + "="*60)
    print("Installing Dependencies")
    print("="*60)

    response = input("\nInstall required packages? (y/n): ")
    if response.lower() != 'y':
        print("Skipping dependency installation")
        return True

    import subprocess

    try:
        print("\nInstalling packages from requirements.txt...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        return False


def test_configuration():
    """Test the configuration."""
    print("\n" + "="*60)
    print("Testing Configuration")
    print("="*60)

    response = input("\nTest API connections? (y/n): ")
    if response.lower() != 'y':
        print("Skipping connection tests")
        return True

    try:
        # Import after dependencies are installed
        from coordinator import DailyBriefCoordinator
        from config import Config

        print("\nValidating configuration...")
        Config.validate()
        print("✓ Configuration valid")

        print("\nTesting API connections...")
        coordinator = DailyBriefCoordinator()
        results = coordinator.test_connections()

        all_passed = all(results.values())

        if all_passed:
            print("\n✓ All API connections successful!")
            return True
        else:
            print("\n⚠️  Some connections failed:")
            for service, status in results.items():
                status_icon = "✓" if status else "✗"
                print(f"   {status_icon} {service}")
            return False

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        return False


def create_launch_agent_helper():
    """Provide instructions for setting up as a launch agent."""
    print("\n" + "="*60)
    print("Automatic Startup Configuration")
    print("="*60)

    print("\nTo run the Daily Brief Agent automatically at 4pm every day:")
    print("\n1. Keep running in terminal:")
    print("   python scheduler.py")

    print("\n2. Run in background with nohup:")
    print("   nohup python scheduler.py > scheduler.log 2>&1 &")

    print("\n3. Run in screen session:")
    print("   screen -S daily-brief")
    print("   python scheduler.py")
    print("   # Press Ctrl+A then D to detach")

    if sys.platform == 'darwin':
        print("\n4. Create macOS Launch Agent (recommended):")
        print("   See docs/setup_launchd.md for instructions")
    elif sys.platform == 'linux':
        print("\n4. Create systemd service (recommended):")
        print("   See docs/setup_systemd.md for instructions")


def main():
    """Main setup flow."""
    print("="*60)
    print("Daily Brief Agent - Setup")
    print("="*60)

    # Check Python version
    if not check_python_version():
        return False

    # Check virtual environment
    if not check_virtual_env():
        return False

    # Create .env file
    if not create_env_file():
        return False

    # Install dependencies
    if not install_dependencies():
        print("\n⚠️  Continue with API key setup anyway")

    # Configure API keys
    if not prompt_for_api_keys():
        return False

    # Test configuration
    test_configuration()

    # Provide launch agent instructions
    create_launch_agent_helper()

    print("\n" + "="*60)
    print("Setup Complete!")
    print("="*60)
    print("\nNext steps:")
    print("1. Review your .env file and ensure all keys are correct")
    print("2. Test manually with: python coordinator.py")
    print("3. Start scheduler with: python scheduler.py")
    print("\nFor help, see README.md")

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(1)
