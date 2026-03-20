#!/usr/bin/env python3
"""Test the @mention subtask creation against real Asana API.

Creates a test parent task with mock mention subtasks, verifies the structure,
then cleans up by deleting the test tasks.

IMPORTANT: This script creates REAL Asana tasks visible to the whole team.
Run with --confirm to actually create tasks. Without that flag, it runs in
dry-run mode (prints what would happen, no API calls).
"""
import sys
from config import Config
from integrations.asana_client import AsanaClient

def test_mention_subtasks():
    """Test creating a mention task with subtasks."""
    print("\n📬 Testing @Mention Subtask Creation")
    print("=" * 50)

    # Initialize client
    try:
        client = AsanaClient()
        print("✓ AsanaClient initialized")
    except Exception as e:
        print(f"✗ Failed to initialize AsanaClient: {e}")
        return False

    # Create mock mentions (simulating what the system would generate)
    mock_mentions = [
        {
            'task_gid': '12345',
            'task_name': 'Q1 Budget Review',
            'task_url': 'https://app.asana.com/0/0/12345',
            'project_name': 'Finance',
            'mentioned_user_name': Config.YOUR_NAME,
            'author_name': 'Jack Shannon',
            'comment_text': 'Hey @Deuce can you review the updated numbers?',
            'hours_since_mention': 3.5,
            'response_confidence': 'high',
            'suggested_response': "Sure, I'll take a look at the updated numbers today.",
            'mention_story_gid': 'story_001',
        },
        {
            'task_gid': '67890',
            'task_name': 'Sprint Planning Notes',
            'task_url': 'https://app.asana.com/0/0/67890',
            'project_name': 'Engineering',
            'mentioned_user_name': Config.YOUR_NAME,
            'author_name': 'Sarah Lee',
            'comment_text': '@Deuce what do you think about pushing the deadline?',
            'hours_since_mention': 28,
            'response_confidence': 'medium',
            'suggested_response': "I think we should discuss this in our next standup.",
            'mention_story_gid': 'story_002',
        },
        {
            'task_gid': '11111',
            'task_name': 'Design System Update',
            'task_url': 'https://app.asana.com/0/0/11111',
            'project_name': 'Product',
            'mentioned_user_name': Config.YOUR_NAME,
            'author_name': 'Jack Shannon',
            'comment_text': '@Deuce the new components are ready for review',
            'hours_since_mention': 0.5,
            'response_confidence': 'low',
            'suggested_response': "Thanks, I'll check them out.",
            'mention_story_gid': 'story_003',
        },
    ]

    print(f"\n📋 Creating test task with {len(mock_mentions)} mock mentions...")
    print(f"   Assignee: {Config.YOUR_NAME}")

    # Create the task with subtasks
    try:
        result, subtasked_mentions = client.create_respond_to_mentions_task(
            mock_mentions,
            assignee_name=Config.YOUR_NAME
        )

        if not result:
            print("✗ No result returned from task creation")
            return False

        parent_gid = result['gid']
        print(f"✓ Parent task created: {parent_gid}")
        print(f"   Name: {result.get('name')}")
        print(f"   Subtasks tracked: {len(subtasked_mentions)}/{len(mock_mentions)}")

    except Exception as e:
        print(f"✗ Failed to create task: {e}")
        return False

    # Verify subtasks were created
    print("\n🔍 Verifying subtasks...")
    try:
        subtasks = client.tasks_api.get_subtasks_for_task(
            parent_gid,
            opts={'opt_fields': 'name,notes,assignee,assignee.name'}
        )

        subtask_list = list(subtasks)
        print(f"✓ Found {len(subtask_list)} subtasks (expected {len(mock_mentions)})")

        if len(subtask_list) != len(mock_mentions):
            print(f"✗ Subtask count mismatch! Expected {len(mock_mentions)}, got {len(subtask_list)}")

        for i, subtask in enumerate(subtask_list, 1):
            name = subtask.get('name', 'Unknown')
            print(f"   {i}. {name}")

            # Verify subtask has notes
            full_subtask = client.tasks_api.get_task(subtask['gid'], opts={'opt_fields': 'notes'})
            notes = full_subtask.get('notes', '')
            has_link = '🔗 Link:' in notes
            has_comment = '💬 Comment:' in notes
            has_draft = 'Draft Response' in notes
            print(f"      Notes: {'✓' if notes else '✗'} | Link: {'✓' if has_link else '✗'} | Comment: {'✓' if has_comment else '✗'} | Draft: {'✓' if has_draft else '✗'}")

        success = len(subtask_list) == len(mock_mentions)

    except Exception as e:
        print(f"✗ Failed to verify subtasks: {e}")
        success = False
        subtask_list = []

    # Clean up: delete the test task and subtasks
    print("\n🧹 Cleaning up test tasks...")
    try:
        # Delete subtasks first
        for subtask in subtask_list:
            client.tasks_api.delete_task(subtask['gid'])
            print(f"   Deleted subtask: {subtask['gid']}")

        # Delete parent task
        client.tasks_api.delete_task(parent_gid)
        print(f"   Deleted parent: {parent_gid}")
        print("✓ Cleanup complete")
    except Exception as e:
        print(f"⚠ Cleanup failed (you may need to manually delete task {parent_gid}): {e}")

    # Summary
    print("\n" + "=" * 50)
    if success:
        print("✅ TEST PASSED: Subtasks created correctly!")
    else:
        print("❌ TEST FAILED: Check output above for details")

    return success


if __name__ == '__main__':
    if '--confirm' not in sys.argv:
        print("\n⚠️  DRY-RUN MODE (no API calls made)")
        print("   This script creates REAL Asana tasks visible to the whole team.")
        print("   Run with --confirm to actually create and clean up test tasks.")
        print("\n   Would create a parent task with 3 mock mentions assigned to:", Config.YOUR_NAME)
        print("   Mentions: 'Q1 Budget Review', 'Sprint Planning Notes', 'Design System Update'")
        print("\n   To run for real: python test_mention_subtasks.py --confirm")
        sys.exit(0)

    success = test_mention_subtasks()
    sys.exit(0 if success else 1)
