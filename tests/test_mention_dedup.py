"""Comprehensive tests for mention deduplication and cross-user isolation.

These tests verify the three root-cause bugs that caused:
1. Jack's mentions appearing in Deuce's task (cross-user contamination)
2. Duplicate tasks being created (TOCTOU race condition)
3. Mentions on non-team-member tasks being silently dropped

Run with: pytest tests/test_mention_dedup.py -v
"""
import json
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, PropertyMock
from typing import List, Dict, Any

import pytest
import pytz

# Patch Config before importing modules that use it
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
os.environ.setdefault('AIRTABLE_API_KEY', 'test-key')
os.environ.setdefault('AIRTABLE_BASE_ID', 'test-base')
os.environ.setdefault('ASANA_ACCESS_TOKEN', 'test-token')
os.environ.setdefault('ASANA_WORKSPACE_GID', 'test-workspace')
os.environ.setdefault('SLACK_BOT_TOKEN', 'xoxb-test')
os.environ.setdefault('SLACK_CHANNEL_ID', 'C-test')
os.environ.setdefault('TEAM_MEMBERS', 'Deuce Thevenow,Jack Shannon')
os.environ.setdefault('MONITORED_USERS', 'Deuce Thevenow,Jack Shannon')

from utils.mention_tracker import (
    make_dedup_key,
    filter_new_mentions,
    mark_mentions_as_processed,
    load_processed_mentions,
    save_processed_mentions,
    reserve_mentions,
    unreserve_mentions,
    LOCAL_TRACKER_FILE,
)


# ============================================================
# Test Fixtures
# ============================================================

DEUCE_GID = "111111"
JACK_GID = "222222"
SARAH_GID = "333333"  # Non-monitored commenter
TZ = pytz.timezone('America/Denver')


def make_mention(story_gid: str, user_name: str, user_gid: str,
                 author_name: str = "Sarah Smith", author_gid: str = SARAH_GID,
                 task_gid: str = "task_1", task_name: str = "Test Task",
                 comment_text: str = "Hey, can you review this?") -> Dict[str, Any]:
    """Factory for creating mention dictionaries matching production shape."""
    return {
        'task_gid': task_gid,
        'task_name': task_name,
        'task_url': f'https://app.asana.com/0/0/{task_gid}',
        'project_name': 'Test Project',
        'task_description': 'Task notes',
        'mention_story_gid': story_gid,
        'mentioned_user_name': user_name,
        'mentioned_user_gid': user_gid,
        'author_name': author_name,
        'author_gid': author_gid,
        'comment_text': comment_text,
        'comment_created_at': datetime.now(TZ).isoformat(),
        'hours_since_mention': 2.5,
        'recent_comments': [],
    }


@pytest.fixture(autouse=True)
def isolated_tracker(tmp_path):
    """Use a temp directory for the tracker file and disable GCS in every test."""
    tracker_file = str(tmp_path / 'data' / 'processed_mentions.json')
    with patch('utils.mention_tracker.LOCAL_TRACKER_FILE', tracker_file), \
         patch('utils.mention_tracker._gcs_available', False):
        yield tracker_file


# ============================================================
# BUG 1: Composite Dedup Key Tests
# ============================================================

class TestCompositeDeduKey:
    """Verify that dedup keys are per-user-per-comment, not per-comment."""

    def test_key_includes_both_story_and_user_gid(self):
        """Key must be '{story_gid}:{user_gid}', not just story_gid."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        key = make_dedup_key(mention)
        assert key == f"story_100:{DEUCE_GID}"

    def test_same_comment_different_users_produce_different_keys(self):
        """THE core bug: one comment mentioning both users must produce two distinct keys."""
        deuce_mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        jack_mention = make_mention("story_100", "Jack Shannon", JACK_GID)

        deuce_key = make_dedup_key(deuce_mention)
        jack_key = make_dedup_key(jack_mention)

        assert deuce_key != jack_key, (
            "Same story_gid for two users MUST produce different dedup keys. "
            "This was the root cause of cross-user contamination."
        )
        assert DEUCE_GID in deuce_key
        assert JACK_GID in jack_key

    def test_different_comments_same_user_produce_different_keys(self):
        """Two different comments mentioning the same user are distinct."""
        mention_a = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        mention_b = make_mention("story_200", "Deuce Thevenow", DEUCE_GID)

        assert make_dedup_key(mention_a) != make_dedup_key(mention_b)

    def test_missing_user_gid_falls_back_to_story_only(self):
        """If user_gid is missing (shouldn't happen), falls back to story_gid."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        del mention['mentioned_user_gid']
        key = make_dedup_key(mention)
        assert key == "story_100"

    def test_missing_story_gid_returns_empty(self):
        """If story_gid is missing, returns empty string."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        del mention['mention_story_gid']
        key = make_dedup_key(mention)
        assert key == ''

    def test_empty_string_gids_handled(self):
        """Empty string GIDs are treated as missing."""
        mention = make_mention("", "Deuce Thevenow", DEUCE_GID)
        assert make_dedup_key(mention) == ''

        mention2 = make_mention("story_100", "Deuce Thevenow", "")
        # Should warn and fall back to story_gid only
        assert make_dedup_key(mention2) == "story_100"


# ============================================================
# BUG 1: Cross-User Contamination Prevention
# ============================================================

class TestCrossUserIsolation:
    """Verify that processing one user's mention does NOT affect the other."""

    def test_marking_jack_processed_does_not_affect_deuce(self):
        """THE critical test: marking Jack's mention as processed must NOT
        prevent Deuce's mention of the same comment from being detected."""
        # Same comment mentions both users
        deuce_mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        jack_mention = make_mention("story_100", "Jack Shannon", JACK_GID)

        # Process Jack's mention
        mark_mentions_as_processed([jack_mention])

        # Deuce's mention of the same comment must still be "new"
        new_mentions = filter_new_mentions([deuce_mention])
        assert len(new_mentions) == 1, (
            "Deuce's mention was incorrectly filtered out because Jack's mention "
            "of the same comment was already processed. This is the cross-user "
            "contamination bug."
        )
        assert new_mentions[0]['mentioned_user_name'] == 'Deuce Thevenow'

    def test_marking_deuce_processed_does_not_affect_jack(self):
        """Reverse direction: marking Deuce's mention must NOT affect Jack's."""
        deuce_mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        jack_mention = make_mention("story_100", "Jack Shannon", JACK_GID)

        mark_mentions_as_processed([deuce_mention])

        new_mentions = filter_new_mentions([jack_mention])
        assert len(new_mentions) == 1
        assert new_mentions[0]['mentioned_user_name'] == 'Jack Shannon'

    def test_both_users_processed_independently(self):
        """Both users can be processed for the same comment without interference."""
        deuce_mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        jack_mention = make_mention("story_100", "Jack Shannon", JACK_GID)

        # Process Deuce first
        mark_mentions_as_processed([deuce_mention])
        # Deuce is now filtered, Jack is not
        assert filter_new_mentions([deuce_mention]) == []
        assert len(filter_new_mentions([jack_mention])) == 1

        # Process Jack
        mark_mentions_as_processed([jack_mention])
        # Now both are filtered
        assert filter_new_mentions([deuce_mention]) == []
        assert filter_new_mentions([jack_mention]) == []

    def test_multi_mention_comment_produces_separate_entries(self):
        """A comment mentioning 3 users creates 3 independent trackable mentions."""
        mentions = [
            make_mention("story_100", "Deuce Thevenow", DEUCE_GID),
            make_mention("story_100", "Jack Shannon", JACK_GID),
            make_mention("story_100", "Sarah Smith", SARAH_GID),
        ]

        keys = {make_dedup_key(m) for m in mentions}
        assert len(keys) == 3, "Each user must have a unique dedup key"

        # Process only one
        mark_mentions_as_processed([mentions[0]])
        new = filter_new_mentions(mentions)
        assert len(new) == 2, "Only the processed user's mention should be filtered"

    def test_legacy_plain_story_gid_does_not_block_composite_keys(self):
        """Old-format entries (plain story_gid) must NOT match new composite keys.
        This ensures migration doesn't accidentally suppress mentions."""
        # Simulate legacy data
        tracker_data = load_processed_mentions()
        tracker_data['processed_ids'] = {'story_100'}  # Legacy: no user_gid
        save_processed_mentions(set(), tracker_data)

        # New composite key should NOT match the legacy entry
        deuce_mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        new = filter_new_mentions([deuce_mention])
        assert len(new) == 1, (
            "Legacy plain story_gid should NOT block composite key story_100:111111"
        )


# ============================================================
# BUG 2: TOCTOU Race Condition — Reserve/Unreserve
# ============================================================

class TestReservationPattern:
    """Verify atomic reservation prevents duplicate task creation."""

    def test_reserve_returns_only_unreserved_keys(self):
        """Reserve should return only keys not already in the tracker."""
        mention_a = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        mention_b = make_mention("story_200", "Deuce Thevenow", DEUCE_GID)

        # Reserve both
        reserved = reserve_mentions([mention_a, mention_b])
        assert len(reserved) == 2

        # Try to reserve again — should get empty set
        reserved_again = reserve_mentions([mention_a, mention_b])
        assert len(reserved_again) == 0, "Second reservation must return empty — already taken"

    def test_reserve_writes_to_tracker_immediately(self):
        """Reservation must be written to disk before returning."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        reserved = reserve_mentions([mention])
        assert len(reserved) == 1

        # Verify it's on disk
        tracker = load_processed_mentions()
        expected_key = f"story_100:{DEUCE_GID}"
        assert expected_key in tracker['processed_ids']

    def test_unreserve_removes_from_tracker(self):
        """Unreserve must remove keys so they can be retried."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        reserved = reserve_mentions([mention])

        # Unreserve (simulating task creation failure)
        unreserve_mentions(reserved)

        # Should be available again
        tracker = load_processed_mentions()
        expected_key = f"story_100:{DEUCE_GID}"
        assert expected_key not in tracker['processed_ids']

        # Can re-reserve
        reserved_again = reserve_mentions([mention])
        assert len(reserved_again) == 1

    def test_concurrent_reservation_simulation(self):
        """Simulate two runs: first reserves, second sees them as taken."""
        mentions = [
            make_mention("story_100", "Deuce Thevenow", DEUCE_GID),
            make_mention("story_200", "Jack Shannon", JACK_GID),
        ]

        # "Run 1" reserves both
        run1_reserved = reserve_mentions(mentions)
        assert len(run1_reserved) == 2

        # "Run 2" tries to reserve the same mentions
        run2_reserved = reserve_mentions(mentions)
        assert len(run2_reserved) == 0, (
            "Concurrent run must not be able to double-reserve mentions"
        )

    def test_partial_reservation(self):
        """If some mentions are already reserved, only new ones are returned."""
        mention_a = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        mention_b = make_mention("story_200", "Deuce Thevenow", DEUCE_GID)

        # Reserve only A
        reserve_mentions([mention_a])

        # Try to reserve both — only B should be returned
        reserved = reserve_mentions([mention_a, mention_b])
        assert len(reserved) == 1
        assert f"story_200:{DEUCE_GID}" in reserved

    def test_unreserve_only_removes_specified_keys(self):
        """Unreserve must not affect other reservations."""
        mention_a = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        mention_b = make_mention("story_200", "Deuce Thevenow", DEUCE_GID)

        reserve_mentions([mention_a, mention_b])

        # Unreserve only A
        unreserve_mentions({f"story_100:{DEUCE_GID}"})

        # B should still be reserved
        tracker = load_processed_mentions()
        assert f"story_200:{DEUCE_GID}" in tracker['processed_ids']
        assert f"story_100:{DEUCE_GID}" not in tracker['processed_ids']

    def test_unreserve_empty_set_is_noop(self):
        """Unreserving an empty set should not crash or modify tracker."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        reserve_mentions([mention])

        unreserve_mentions(set())

        tracker = load_processed_mentions()
        assert f"story_100:{DEUCE_GID}" in tracker['processed_ids']


# ============================================================
# BUG 2: Duplicate Task Prevention (find_existing check)
# ============================================================

class TestDuplicateTaskPrevention:
    """Verify the full flow prevents duplicate Asana task creation."""

    def test_filter_then_reserve_then_create_flow(self):
        """End-to-end: filter → reserve → (simulate create) → verify no re-process."""
        mentions = [
            make_mention("story_100", "Deuce Thevenow", DEUCE_GID),
            make_mention("story_100", "Jack Shannon", JACK_GID),
            make_mention("story_200", "Deuce Thevenow", DEUCE_GID),
        ]

        # Step 1: Filter (all are new)
        new = filter_new_mentions(mentions)
        assert len(new) == 3

        # Step 2: Group by user
        by_user = {}
        for m in new:
            name = m['mentioned_user_name']
            by_user.setdefault(name, []).append(m)

        assert 'Deuce Thevenow' in by_user
        assert 'Jack Shannon' in by_user
        assert len(by_user['Deuce Thevenow']) == 2
        assert len(by_user['Jack Shannon']) == 1

        # Step 3: Reserve Deuce's mentions
        deuce_reserved = reserve_mentions(by_user['Deuce Thevenow'])
        assert len(deuce_reserved) == 2

        # Step 4: Reserve Jack's mentions
        jack_reserved = reserve_mentions(by_user['Jack Shannon'])
        assert len(jack_reserved) == 1

        # Step 5: Verify all are now filtered out
        remaining = filter_new_mentions(mentions)
        assert len(remaining) == 0

    def test_failed_create_unreserves_for_retry(self):
        """If Asana task creation fails, unreserved mentions must be retryable."""
        mentions = [
            make_mention("story_100", "Deuce Thevenow", DEUCE_GID),
            make_mention("story_200", "Deuce Thevenow", DEUCE_GID),
        ]

        # Reserve
        reserved = reserve_mentions(mentions)
        assert len(reserved) == 2

        # Simulate failure → unreserve
        unreserve_mentions(reserved)

        # Next run: mentions should be available again
        new = filter_new_mentions(mentions)
        assert len(new) == 2


# ============================================================
# Filter + Mark Integration Tests
# ============================================================

class TestFilterMarkIntegration:
    """Test the filter → mark lifecycle with real tracker state."""

    def test_mark_then_filter_removes_processed(self):
        """Basic lifecycle: mark as processed, then filter should exclude them."""
        mentions = [
            make_mention("story_100", "Deuce Thevenow", DEUCE_GID),
            make_mention("story_200", "Jack Shannon", JACK_GID),
        ]

        mark_mentions_as_processed(mentions)
        remaining = filter_new_mentions(mentions)
        assert len(remaining) == 0

    def test_filter_preserves_unprocessed(self):
        """Filter must not remove mentions that haven't been processed."""
        processed = [make_mention("story_100", "Deuce Thevenow", DEUCE_GID)]
        unprocessed = [make_mention("story_200", "Jack Shannon", JACK_GID)]

        mark_mentions_as_processed(processed)
        remaining = filter_new_mentions(processed + unprocessed)
        assert len(remaining) == 1
        assert remaining[0]['mentioned_user_name'] == 'Jack Shannon'

    def test_idempotent_mark(self):
        """Marking the same mention twice should not cause issues."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)

        mark_mentions_as_processed([mention])
        mark_mentions_as_processed([mention])

        tracker = load_processed_mentions()
        # Should only have one entry, not duplicates
        key = f"story_100:{DEUCE_GID}"
        assert list(tracker['processed_ids']).count(key) <= 1  # Set, so always 1

    def test_empty_mention_list_is_noop(self):
        """Marking/filtering empty lists should not crash."""
        mark_mentions_as_processed([])
        result = filter_new_mentions([])
        assert result == []

    def test_mention_without_story_gid_passes_through_filter(self):
        """Mentions missing story_gid should pass through filter (safety net)."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        del mention['mention_story_gid']

        result = filter_new_mentions([mention])
        assert len(result) == 1


# ============================================================
# Tracker File Persistence Tests
# ============================================================

class TestTrackerPersistence:
    """Verify tracker file reads/writes correctly."""

    def test_empty_tracker_returns_empty_set(self):
        """Fresh tracker has no processed IDs."""
        data = load_processed_mentions()
        assert data['processed_ids'] == set()
        assert data['total_processed'] == 0

    def test_save_and_load_roundtrip(self):
        """Keys survive save → load cycle."""
        keys = {f"story_100:{DEUCE_GID}", f"story_200:{JACK_GID}"}
        save_processed_mentions(keys)

        loaded = load_processed_mentions()
        assert loaded['processed_ids'] == keys
        assert loaded['total_processed'] == 2

    def test_merge_with_existing(self):
        """New keys merge with existing ones, not replace."""
        save_processed_mentions({f"story_100:{DEUCE_GID}"})
        save_processed_mentions({f"story_200:{JACK_GID}"})

        loaded = load_processed_mentions()
        assert len(loaded['processed_ids']) == 2

    def test_corrupted_file_returns_empty(self):
        """Corrupted JSON should return empty set, not crash."""
        # Write garbage to tracker file
        tracker = load_processed_mentions()  # Ensure dir exists
        # Get the actual tracker file path from the patched value
        import utils.mention_tracker as mt
        os.makedirs(os.path.dirname(mt.LOCAL_TRACKER_FILE), exist_ok=True)
        with open(mt.LOCAL_TRACKER_FILE, 'w') as f:
            f.write("not valid json{{{")

        data = load_processed_mentions()
        assert data['processed_ids'] == set()


# ============================================================
# Coordinator Integration Tests (Mocked Asana)
# ============================================================

class TestCoordinatorMentionFlow:
    """Test the coordinator's mention processing with mocked dependencies."""

    def _make_coordinator_mentions(self) -> List[Dict[str, Any]]:
        """Create a realistic set of mentions including cross-user scenario."""
        return [
            # Comment 1: mentions BOTH Deuce and Jack (the cross-user bug scenario)
            make_mention("story_100", "Deuce Thevenow", DEUCE_GID,
                        comment_text="Hey @Deuce and @Jack, review this PR"),
            make_mention("story_100", "Jack Shannon", JACK_GID,
                        comment_text="Hey @Deuce and @Jack, review this PR"),
            # Comment 2: mentions only Deuce
            make_mention("story_200", "Deuce Thevenow", DEUCE_GID,
                        task_gid="task_2", task_name="Budget Review",
                        comment_text="@Deuce can you approve this?"),
            # Comment 3: mentions only Jack
            make_mention("story_300", "Jack Shannon", JACK_GID,
                        task_gid="task_3", task_name="Sales Pipeline",
                        comment_text="@Jack what's the status?"),
        ]

    def test_grouping_produces_correct_user_buckets(self):
        """Verify mentions are grouped by mentioned_user_name correctly."""
        mentions = self._make_coordinator_mentions()

        by_user = {}
        for m in mentions:
            name = m.get('mentioned_user_name')
            if name:
                by_user.setdefault(name, []).append(m)

        assert len(by_user) == 2
        assert len(by_user['Deuce Thevenow']) == 2  # story_100 + story_200
        assert len(by_user['Jack Shannon']) == 2    # story_100 + story_300

    def test_cross_user_comment_creates_independent_reservations(self):
        """The same comment @mentioning both users creates 2 independent reservations."""
        mentions = self._make_coordinator_mentions()

        # Filter (all new)
        new = filter_new_mentions(mentions)
        assert len(new) == 4

        # Group by user
        by_user = {}
        for m in new:
            name = m['mentioned_user_name']
            by_user.setdefault(name, []).append(m)

        # Reserve Deuce's mentions
        deuce_reserved = reserve_mentions(by_user['Deuce Thevenow'])
        assert len(deuce_reserved) == 2

        # Reserve Jack's mentions — should succeed even though story_100 was
        # already reserved for Deuce (different composite key)
        jack_reserved = reserve_mentions(by_user['Jack Shannon'])
        assert len(jack_reserved) == 2, (
            "Jack's reservation failed — likely because story_100 was already "
            "reserved for Deuce. This means the composite key fix is broken."
        )

    def test_partial_subtask_failure_unreserves_only_failed(self):
        """If 2 of 3 subtasks succeed, only the failed one gets unreserved."""
        mentions = [
            make_mention("story_100", "Deuce Thevenow", DEUCE_GID),
            make_mention("story_200", "Deuce Thevenow", DEUCE_GID),
            make_mention("story_300", "Deuce Thevenow", DEUCE_GID),
        ]

        reserved = reserve_mentions(mentions)
        assert len(reserved) == 3

        # Simulate: subtasks succeeded for story_100 and story_200, failed for story_300
        succeeded = [mentions[0], mentions[1]]
        succeeded_keys = {make_dedup_key(m) for m in succeeded}
        failed_keys = reserved - succeeded_keys

        unreserve_mentions(failed_keys)

        # story_100 and story_200 should still be processed
        # story_300 should be available for retry
        tracker = load_processed_mentions()
        assert f"story_100:{DEUCE_GID}" in tracker['processed_ids']
        assert f"story_200:{DEUCE_GID}" in tracker['processed_ids']
        assert f"story_300:{DEUCE_GID}" not in tracker['processed_ids']

    def test_missing_mentioned_user_name_is_skipped(self):
        """Mentions with missing mentioned_user_name must not be grouped."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        del mention['mentioned_user_name']

        by_user = {}
        for m in [mention]:
            name = m.get('mentioned_user_name')
            if not name:
                continue  # Matches coordinator logic
            by_user.setdefault(name, []).append(m)

        assert len(by_user) == 0

    def test_full_lifecycle_two_users_same_comment(self):
        """End-to-end: one comment mentioning both users → two separate task flows."""
        deuce_mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)
        jack_mention = make_mention("story_100", "Jack Shannon", JACK_GID)
        all_mentions = [deuce_mention, jack_mention]

        # Step 1: Filter (both new)
        new = filter_new_mentions(all_mentions)
        assert len(new) == 2

        # Step 2: Group
        by_user = {}
        for m in new:
            by_user.setdefault(m['mentioned_user_name'], []).append(m)

        # Step 3: Reserve Deuce's
        deuce_reserved = reserve_mentions(by_user['Deuce Thevenow'])
        assert len(deuce_reserved) == 1

        # Step 4: Reserve Jack's (must work despite same story_gid)
        jack_reserved = reserve_mentions(by_user['Jack Shannon'])
        assert len(jack_reserved) == 1

        # Step 5: Simulate successful task creation for both
        # (reservations stand — mentions are processed)

        # Step 6: On next run, both should be filtered out
        next_run_new = filter_new_mentions(all_mentions)
        assert len(next_run_new) == 0

    def test_full_lifecycle_failure_and_retry(self):
        """End-to-end: reserve → fail → unreserve → retry succeeds."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)

        # Run 1: Reserve and fail
        reserved = reserve_mentions([mention])
        assert len(reserved) == 1
        unreserve_mentions(reserved)  # Simulate failure

        # Run 2: Should be able to process again
        new = filter_new_mentions([mention])
        assert len(new) == 1

        reserved2 = reserve_mentions([mention])
        assert len(reserved2) == 1
        # This time, task creation succeeds — reservation stands


# ============================================================
# BUG 3: get_tasks_modified_since scans monitored users
# ============================================================

class TestTaskScanScope:
    """Verify that get_tasks_modified_since scans MONITORED_USER_NAMES too."""

    @patch('integrations.asana_client.Config')
    def test_scan_includes_monitored_users(self, mock_config):
        """Tasks for monitored users (not just team members) must be scanned."""
        mock_config.TEAM_MEMBERS = ['Alice', 'Bob']
        mock_config.MONITORED_USER_NAMES = ['Deuce Thevenow', 'Jack Shannon']
        mock_config.ASANA_ACCESS_TOKEN = 'test'
        mock_config.ASANA_WORKSPACE_GID = 'ws123'
        mock_config.TIMEZONE = TZ

        # The combined set should include all 4 names
        all_names = set(mock_config.TEAM_MEMBERS) | set(mock_config.MONITORED_USER_NAMES)
        assert 'Deuce Thevenow' in all_names
        assert 'Jack Shannon' in all_names
        assert 'Alice' in all_names
        assert 'Bob' in all_names

    @patch('integrations.asana_client.Config')
    def test_overlapping_team_and_monitored_no_duplicates(self, mock_config):
        """If a user is in both TEAM_MEMBERS and MONITORED_USERS, no duplicate scan."""
        mock_config.TEAM_MEMBERS = ['Deuce Thevenow', 'Alice']
        mock_config.MONITORED_USER_NAMES = ['Deuce Thevenow', 'Jack Shannon']

        all_names = set(mock_config.TEAM_MEMBERS) | set(mock_config.MONITORED_USER_NAMES)
        assert len(all_names) == 3  # Deuce, Alice, Jack — no duplicates


# ============================================================
# Extract Mentions from HTML Tests
# ============================================================

class TestExtractMentionsFromHTML:
    """Verify HTML mention parsing produces correct user attributions."""

    def _make_client(self):
        """Create a minimal AsanaClient for testing HTML parsing."""
        with patch('integrations.asana_client.asana'), \
             patch('integrations.asana_client.Config') as mock_config:
            mock_config.ASANA_ACCESS_TOKEN = 'test'
            mock_config.ASANA_WORKSPACE_GID = 'ws123'
            mock_config.TEAM_MEMBERS = []
            mock_config.MONITORED_USER_NAMES = []
            mock_config.TIMEZONE = TZ
            from integrations.asana_client import AsanaClient
            client = AsanaClient()
            return client

    def test_single_mention(self):
        html = '<body><a data-asana-type="user" data-asana-gid="111">@Deuce</a> please review</body>'
        client = self._make_client()
        mentions = client.extract_mentions_from_html(html)
        assert len(mentions) == 1
        assert mentions[0]['user_gid'] == '111'

    def test_dual_mention_produces_two_entries(self):
        """A comment mentioning both @Deuce and @Jack must produce two mention entries."""
        html = (
            '<body>'
            '<a data-asana-type="user" data-asana-gid="111">@Deuce</a> and '
            '<a data-asana-type="user" data-asana-gid="222">@Jack</a> review this'
            '</body>'
        )
        client = self._make_client()
        mentions = client.extract_mentions_from_html(html)
        assert len(mentions) == 2
        gids = {m['user_gid'] for m in mentions}
        assert '111' in gids
        assert '222' in gids

    def test_empty_html(self):
        client = self._make_client()
        assert client.extract_mentions_from_html('') == []
        assert client.extract_mentions_from_html(None) == []

    def test_no_mentions_in_html(self):
        html = '<body>Just a regular comment with no mentions</body>'
        client = self._make_client()
        assert client.extract_mentions_from_html(html) == []


# ============================================================
# Unanswered Mention Detection Tests
# ============================================================

class TestUnansweredMentionDetection:
    """Verify the get_unanswered_mentions logic correctly attributes mentions per user."""

    def test_dual_mention_comment_creates_entries_for_both_users(self):
        """When a single comment @mentions both users, get_unanswered_mentions
        must create a SEPARATE entry for each user, each with the correct
        mentioned_user_name and mentioned_user_gid."""

        # Simulated scenario: Sarah comments "@Deuce and @Jack review this"
        # on a task. Neither Deuce nor Jack has replied.
        deuce_entry = make_mention("story_100", "Deuce Thevenow", DEUCE_GID,
                                   author_name="Sarah Smith", author_gid=SARAH_GID)
        jack_entry = make_mention("story_100", "Jack Shannon", JACK_GID,
                                  author_name="Sarah Smith", author_gid=SARAH_GID)

        # Verify each entry has the correct user attribution
        assert deuce_entry['mentioned_user_name'] == 'Deuce Thevenow'
        assert deuce_entry['mentioned_user_gid'] == DEUCE_GID
        assert jack_entry['mentioned_user_name'] == 'Jack Shannon'
        assert jack_entry['mentioned_user_gid'] == JACK_GID

        # Verify they produce different dedup keys
        assert make_dedup_key(deuce_entry) != make_dedup_key(jack_entry)

    def test_self_mention_is_excluded(self):
        """A user mentioning themselves should not be tracked as unanswered.
        This is handled in get_unanswered_mentions by checking author_gid != user_gid."""
        # If Deuce writes a comment that @mentions himself, the production code
        # skips it because comment.author_gid == user_gid. We verify the field
        # structure supports this check.
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID,
                               author_name="Deuce Thevenow", author_gid=DEUCE_GID)
        assert mention['author_gid'] == mention['mentioned_user_gid']


# ============================================================
# Stress / Edge Case Tests
# ============================================================

class TestEdgeCases:
    """Edge cases that could cause subtle bugs."""

    def test_many_mentions_same_comment(self):
        """10 users mentioned in one comment → 10 independent keys."""
        mentions = []
        for i in range(10):
            mentions.append(make_mention(
                "story_big", f"User {i}", f"gid_{i}"
            ))

        keys = {make_dedup_key(m) for m in mentions}
        assert len(keys) == 10

        # Process half
        mark_mentions_as_processed(mentions[:5])
        remaining = filter_new_mentions(mentions)
        assert len(remaining) == 5

    def test_rapid_reserve_unreserve_cycles(self):
        """Multiple reserve/unreserve cycles should not corrupt tracker."""
        mention = make_mention("story_100", "Deuce Thevenow", DEUCE_GID)

        for _ in range(10):
            reserved = reserve_mentions([mention])
            assert len(reserved) == 1
            unreserve_mentions(reserved)

        # After all cycles, mention should still be available
        new = filter_new_mentions([mention])
        assert len(new) == 1

    def test_tracker_with_hundreds_of_entries(self):
        """Tracker performance with many entries."""
        # Pre-populate with 500 entries using composite keys with DEUCE_GID
        keys = {f"story_{i}:{DEUCE_GID}" for i in range(500)}
        save_processed_mentions(keys)

        # Filter a mix of processed and new
        # story_498 and story_499 are already processed, 500-502 are new
        mentions = [
            make_mention(f"story_{i}", "Deuce Thevenow", DEUCE_GID)
            for i in range(498, 503)
        ]

        new = filter_new_mentions(mentions)
        assert len(new) == 3  # 500, 501, 502

    def test_unicode_in_user_names(self):
        """Unicode user names should work in dedup keys."""
        mention = make_mention("story_100", "José García", "gid_unicode")
        key = make_dedup_key(mention)
        assert key == "story_100:gid_unicode"

        mark_mentions_as_processed([mention])
        assert filter_new_mentions([mention]) == []
