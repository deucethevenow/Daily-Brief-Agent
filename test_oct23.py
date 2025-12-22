#!/usr/bin/env python3
"""Test fetching meetings from Oct 23."""
from datetime import datetime
import pytz
from integrations.airtable_client import AirtableClient

client = AirtableClient()
target_date = datetime(2025, 10, 23).date()
user_email = 'deuce@recess.is'

print(f'Looking for meetings on {target_date} with {user_email}')
print()

# Fetch all records
all_records = client.table.all()

meetings_found = []
for record in all_records:
    fields = record['fields']

    # Filter to Fireflies Call
    source_material = fields.get('Source Material', '')
    if source_material != 'Fireflies Call':
        continue

    # Filter to user's meetings
    host_name = fields.get('Host Name', '')
    participants = fields.get('Participants', '')

    is_user_involved = (
        user_email in host_name or
        user_email in participants
    )

    if not is_user_involved:
        continue

    # Check date
    meeting_date_str = fields.get('Created')
    if meeting_date_str:
        try:
            meeting_date = datetime.fromisoformat(meeting_date_str.replace('Z', '+00:00'))
            meeting_date = meeting_date.astimezone(pytz.timezone('America/Denver')).date()

            if meeting_date == target_date:
                transcript = fields.get('Text', '')
                meetings_found.append({
                    'title': fields.get('Title', 'Untitled'),
                    'date': meeting_date_str,
                    'transcript_length': len(transcript),
                    'transcript_preview': transcript[:200] if transcript else '(no transcript)'
                })
        except Exception as e:
            print(f"Error parsing date: {e}")

print(f'Found {len(meetings_found)} meetings:')
print()

for m in meetings_found:
    print(f"Title: {m['title']}")
    print(f"  Transcript: {m['transcript_length']} characters")
    print(f"  Preview: {m['transcript_preview']}")
    print()
