#!/usr/bin/env python3
"""Inspect Airtable field structure."""
from datetime import datetime
from integrations.airtable_client import AirtableClient

# Initialize client
client = AirtableClient()

print("Fetching sample records from Airtable...")
records = client.table.all(max_records=5)

print(f"\nFound {len(records)} sample records\n")
print("="*60)

for i, record in enumerate(records, 1):
    fields = record['fields']
    print(f"RECORD {i}:")
    print(f"  ID: {record['id']}")
    print(f"  Fields:")

    for key, value in fields.items():
        # Truncate long values
        if isinstance(value, str) and len(value) > 100:
            value_display = value[:100] + "..."
        else:
            value_display = value

        print(f"    - {key}: {value_display}")

    print()
    print("-"*60)
    print()
