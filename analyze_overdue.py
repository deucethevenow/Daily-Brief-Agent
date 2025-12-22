#!/usr/bin/env python3
"""Quick analysis of overdue tasks by team member."""
from integrations.asana_client import AsanaClient
from config import Config
from collections import Counter

# Initialize Asana client
asana = AsanaClient()

# Get overdue tasks
print("Fetching overdue tasks...")
overdue_tasks = asana.get_overdue_tasks()

print(f"\nTotal overdue tasks: {len(overdue_tasks)}")
print("\n" + "="*60)
print("OVERDUE TASKS BY TEAM MEMBER")
print("="*60)

# Count by assignee
assignee_counts = Counter(task['assignee'] for task in overdue_tasks)

# Sort by count (most to least)
for assignee, count in assignee_counts.most_common():
    percentage = (count / len(overdue_tasks)) * 100
    print(f"{assignee:20s}: {count:5d} tasks ({percentage:5.1f}%)")

print("="*60)

# Show top 5 most overdue tasks for the person with most overdue
if assignee_counts:
    top_person = assignee_counts.most_common(1)[0][0]
    print(f"\nTop 5 Most Overdue Tasks for {top_person}:")
    print("-"*60)

    person_tasks = [t for t in overdue_tasks if t['assignee'] == top_person]
    person_tasks.sort(key=lambda x: x['days_overdue'], reverse=True)

    for i, task in enumerate(person_tasks[:5], 1):
        print(f"{i}. [{task['days_overdue']} days] {task['name']}")
        print(f"   Project: {task['project']}")
