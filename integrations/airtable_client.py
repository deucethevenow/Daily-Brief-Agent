"""Airtable client for fetching meeting data."""
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pyairtable import Api
from config import Config
from utils import setup_logger
import requests

logger = setup_logger(__name__)

# Request timeout in seconds (connect, read)
REQUEST_TIMEOUT = (10, 60)  # 10s to connect, 60s to read


class AirtableClient:
    """Client for interacting with Airtable to fetch meeting data."""

    def __init__(self):
        """Initialize the Airtable client with request timeout."""
        # Create a session with timeout
        session = requests.Session()
        # Set default timeout for all requests made through this session
        adapter = requests.adapters.HTTPAdapter(
            max_retries=requests.adapters.Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504]
            )
        )
        session.mount('https://', adapter)

        # Initialize Api with custom session timeout
        self.api = Api(Config.AIRTABLE_API_KEY, timeout=REQUEST_TIMEOUT)
        self.table = self.api.table(Config.AIRTABLE_BASE_ID, Config.AIRTABLE_TABLE_NAME)
        logger.info("AirtableClient initialized with timeout configuration")

    def get_today_meetings(self) -> List[Dict[str, Any]]:
        """Fetch all meetings from today where user was host or participant.

        Returns:
            List of meeting records with fields from Airtable
        """
        today = datetime.now(Config.TIMEZONE).date()
        user_email = 'deuce@recess.is'
        logger.info(f"Fetching meetings for {today} where {user_email} was involved")

        try:
            # Fetch all records from today
            all_records = self.table.all()

            today_meetings = []
            for record in all_records:
                fields = record['fields']

                # Filter to only Fireflies call transcripts (singular "Call", not plural "calls")
                source_material = fields.get('Source Material', '')
                if source_material != 'Fireflies Call':
                    continue  # Skip non-Fireflies records

                # Filter to meetings where deuce@recess.is was host or participant
                host_name = fields.get('Host Name', '')
                participants = fields.get('Participants', '')

                is_user_involved = (
                    user_email in host_name or
                    user_email in participants
                )

                if not is_user_involved:
                    continue  # Skip meetings user wasn't in

                # Use "Created" field for the meeting date
                meeting_date_str = fields.get('Created')

                if meeting_date_str:
                    try:
                        # Parse ISO format
                        meeting_date = datetime.fromisoformat(meeting_date_str.replace('Z', '+00:00'))
                        meeting_date = meeting_date.astimezone(Config.TIMEZONE).date()

                        if meeting_date == today:
                            today_meetings.append({
                                'id': record['id'],
                                'title': fields.get('Title', 'Untitled Meeting'),
                                'date': meeting_date_str,
                                'transcript': fields.get('Text', ''),  # Transcript is in "Text" field
                                'summary': fields.get('Summary', ''),
                                'participants': participants,
                                'host': host_name,
                                'meeting_type': fields.get('Meeting Type', ''),
                                'duration': fields.get('Duration (in seconds)', 0),
                                'raw_fields': fields  # Keep all fields for flexibility
                            })
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not parse date for record {record['id']}: {e}")
                        continue

            logger.info(f"Found {len(today_meetings)} meetings from today where {user_email} was involved")
            return today_meetings

        except Exception as e:
            logger.error(f"Error fetching meetings from Airtable: {e}")
            raise

    def get_week_meetings(self) -> List[Dict[str, Any]]:
        """Fetch all meetings from the current week (Monday to today) where user was host or participant.

        Returns:
            List of meeting records from this week
        """
        today = datetime.now(Config.TIMEZONE).date()
        # Get the Monday of current week
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)

        user_email = 'deuce@recess.is'
        logger.info(f"Fetching meetings from {monday} to {today} where {user_email} was involved")

        try:
            all_records = self.table.all()
            week_meetings = []

            for record in all_records:
                fields = record['fields']

                # Filter to only Fireflies call transcripts (singular "Call")
                source_material = fields.get('Source Material', '')
                if source_material != 'Fireflies Call':
                    continue  # Skip non-Fireflies records

                # Filter to meetings where deuce@recess.is was host or participant
                host_name = fields.get('Host Name', '')
                participants = fields.get('Participants', '')

                is_user_involved = (
                    user_email in host_name or
                    user_email in participants
                )

                if not is_user_involved:
                    continue  # Skip meetings user wasn't in

                # Use "Created" field for the meeting date
                meeting_date_str = fields.get('Created')

                if meeting_date_str:
                    try:
                        meeting_date = datetime.fromisoformat(meeting_date_str.replace('Z', '+00:00'))
                        meeting_date = meeting_date.astimezone(Config.TIMEZONE).date()

                        if monday <= meeting_date <= today:
                            week_meetings.append({
                                'id': record['id'],
                                'title': fields.get('Title', 'Untitled Meeting'),
                                'date': meeting_date_str,
                                'transcript': fields.get('Text', ''),  # Transcript is in "Text" field
                                'summary': fields.get('Summary', ''),
                                'participants': participants,
                                'host': host_name,
                                'meeting_type': fields.get('Meeting Type', ''),
                                'duration': fields.get('Duration (in seconds)', 0),
                                'raw_fields': fields
                            })
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not parse date for record {record['id']}: {e}")
                        continue

            logger.info(f"Found {len(week_meetings)} meetings from this week where {user_email} was involved")
            return week_meetings

        except Exception as e:
            logger.error(f"Error fetching week meetings from Airtable: {e}")
            raise
