#!/usr/bin/env python3
"""Run the daily brief for a specific date."""
import sys
from datetime import datetime
from coordinator import DailyBriefCoordinator
from config import Config
from utils import setup_logger

logger = setup_logger(__name__)

def run_for_date(date_str: str):
    """Run daily brief for a specific date.

    Args:
        date_str: Date in YYYY-MM-DD format
    """
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        logger.info(f"Running daily brief for {target_date.strftime('%Y-%m-%d')}")

        coordinator = DailyBriefCoordinator()

        # Override the date for testing
        import integrations.airtable_client as airtable_module

        # Monkey-patch the get_today_meetings method to use target date
        original_method = coordinator.airtable.get_today_meetings

        def get_target_date_meetings():
            logger.info(f"Fetching meetings for {target_date.strftime('%Y-%m-%d')}")
            records = coordinator.airtable.table.all()

            user_email = 'deuce@recess.is'
            meetings = []
            for record in records:
                fields = record['fields']

                # Filter to only Fireflies call transcripts (singular "Call")
                source_material = fields.get('Source Material', '')
                if source_material != 'Fireflies Call':
                    continue

                # Filter to meetings where deuce@recess.is was host or participant
                host_name = fields.get('Host Name', '')
                participants = fields.get('Participants', '')

                is_user_involved = (
                    user_email in host_name or
                    user_email in participants
                )

                if not is_user_involved:
                    continue

                # Use "Created" field for the meeting date
                date_str_field = fields.get('Created')
                if not date_str_field:
                    continue

                try:
                    meeting_date = datetime.fromisoformat(date_str_field.replace('Z', '+00:00'))
                    meeting_date_only = meeting_date.astimezone(Config.TIMEZONE).date()

                    if meeting_date_only == target_date.date():
                        meetings.append({
                            'id': record['id'],
                            'title': fields.get('Title', 'Untitled Meeting'),
                            'date': date_str_field,
                            'transcript': fields.get('Text', ''),  # Transcript is in "Text" field
                            'summary': fields.get('Summary', ''),
                            'participants': participants,
                            'host': host_name,
                            'meeting_type': fields.get('Meeting Type', ''),
                            'duration': fields.get('Duration (in seconds)', 0),
                            'raw_fields': fields
                        })
                except Exception as e:
                    logger.warning(f"Error parsing date for record {record['id']}: {e}")
                    continue

            logger.info(f"Found {len(meetings)} meetings from {target_date.strftime('%Y-%m-%d')} where {user_email} was involved")
            return meetings

        coordinator.airtable.get_today_meetings = get_target_date_meetings

        # Run the daily brief with the target date override
        # This ensures Friday detection and date formatting work for the test date
        coordinator.run_daily_brief(override_date=target_date)

        logger.info(f"✓ Daily brief for {date_str} completed successfully!")

    except ValueError as e:
        logger.error(f"Invalid date format. Use YYYY-MM-DD: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error running daily brief: {e}")
        raise

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python run_for_date.py YYYY-MM-DD")
        print("Example: python run_for_date.py 2025-10-23")
        sys.exit(1)

    run_for_date(sys.argv[1])
