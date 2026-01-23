"""Configuration management for Daily Brief Agent."""
import os
from pathlib import Path
from dotenv import load_dotenv
import pytz

# Load environment variables
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Configuration class for all API keys and settings."""

    # Anthropic Claude
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

    # Airtable
    AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
    AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
    AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME', 'Meetings')

    # Asana
    ASANA_ACCESS_TOKEN = os.getenv('ASANA_ACCESS_TOKEN')
    ASANA_WORKSPACE_GID = os.getenv('ASANA_WORKSPACE_GID')

    # Slack
    SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
    SLACK_CHANNEL_ID = os.getenv('SLACK_CHANNEL_ID')

    # Timezone
    TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'America/Denver'))

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    # Scheduling
    DAILY_RUN_TIME = "16:00"  # 4:00 PM MT

    # Task Management
    AUTO_CREATE_TASKS = os.getenv('AUTO_CREATE_TASKS', 'false').lower() == 'true'
    YOUR_NAME = os.getenv('YOUR_NAME', '')  # Filter action items to only show yours

    # Team members to track (for Asana task queries)
    _team_members_str = os.getenv('TEAM_MEMBERS', '')
    TEAM_MEMBERS = [name.strip() for name in _team_members_str.split(',') if name.strip()]

    # Only show overdue tasks created within this many days (0 = show all)
    ASANA_TASK_AGE_LIMIT_DAYS = int(os.getenv('ASANA_TASK_AGE_LIMIT_DAYS', '0'))

    # Unanswered @Mentions Monitoring
    # Users to monitor for @mentions (comma-separated names)
    _monitored_users_str = os.getenv('MONITORED_USERS', 'Deuce Thevenow,Jack Shannon')
    MONITORED_USER_NAMES = [name.strip() for name in _monitored_users_str.split(',') if name.strip()]

    # How far back to look for unanswered mentions (in hours)
    MENTION_LOOKBACK_HOURS = int(os.getenv('MENTION_LOOKBACK_HOURS', '168'))  # 7 days

    @classmethod
    def validate(cls):
        """Validate that all required configuration is present."""
        required_vars = [
            ('ANTHROPIC_API_KEY', cls.ANTHROPIC_API_KEY),
            ('AIRTABLE_API_KEY', cls.AIRTABLE_API_KEY),
            ('AIRTABLE_BASE_ID', cls.AIRTABLE_BASE_ID),
            ('ASANA_ACCESS_TOKEN', cls.ASANA_ACCESS_TOKEN),
            ('ASANA_WORKSPACE_GID', cls.ASANA_WORKSPACE_GID),
            ('SLACK_BOT_TOKEN', cls.SLACK_BOT_TOKEN),
            ('SLACK_CHANNEL_ID', cls.SLACK_CHANNEL_ID),
        ]

        missing = [name for name, value in required_vars if not value]

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Please copy .env.example to .env and fill in your API keys."
            )

        return True
