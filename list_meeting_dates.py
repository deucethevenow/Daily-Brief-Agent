#!/usr/bin/env python3
"""List all meeting dates in Airtable."""
from datetime import datetime
from integrations.airtable_client import AirtableClient
from collections import Counter

# Initialize client
client = AirtableClient()

print("Fetching all records from Airtable...")
records = client.table.all()

print(f"\nTotal records: {len(records)}")

# Filter to Fireflies calls
fireflies_dates = []
all_dates = []
source_materials = []

for record in records:
    fields = record['fields']
    source_material = fields.get('source material', '')
    source_materials.append(source_material)

    date_str = fields.get('date')
    if date_str:
        try:
            meeting_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            date_only = meeting_date.date()
            all_dates.append(date_only)

            if source_material == 'Fireflies calls':
                fireflies_dates.append({
                    'date': date_only,
                    'title': fields.get('title', 'Untitled'),
                    'has_transcript': bool(fields.get('transcript', ''))
                })
        except Exception as e:
            print(f"Error parsing date: {e}")

print(f"\n{'='*60}")
print("SOURCE MATERIALS IN DATABASE:")
print(f"{'='*60}")
source_counter = Counter(source_materials)
for source, count in source_counter.most_common():
    print(f"  {source or '(empty)'}: {count} records")

print(f"\n{'='*60}")
print("ALL MEETINGS (any source material):")
print(f"{'='*60}")
date_counter = Counter(all_dates)
for date, count in sorted(date_counter.items(), reverse=True)[:20]:
    print(f"  {date}: {count} meetings")

print(f"\n{'='*60}")
print("FIREFLIES CALLS ONLY:")
print(f"{'='*60}")
if fireflies_dates:
    fireflies_dates.sort(key=lambda x: x['date'], reverse=True)
    for meeting in fireflies_dates[:20]:
        transcript_status = "✓" if meeting['has_transcript'] else "✗"
        print(f"  {meeting['date']} - {meeting['title']} [Transcript: {transcript_status}]")
else:
    print("  No Fireflies calls found!")

print(f"\nTotal Fireflies calls: {len(fireflies_dates)}")
