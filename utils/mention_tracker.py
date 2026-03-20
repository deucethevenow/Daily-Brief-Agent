"""Tracks which @mentions have been processed to avoid duplicates.

CRITICAL: The dedup key is a COMPOSITE of story_gid AND user_gid.
A single comment can @mention multiple users, so story_gid alone is NOT unique.
Using story_gid alone causes cross-user contamination: processing Jack's mention
marks Deuce's mention of the same comment as "done", silently dropping it.

Key format: "{story_gid}:{user_gid}"
Legacy format (story_gid only) is auto-migrated on load.
"""
import json
import os
from datetime import datetime
from typing import Set, List, Dict, Any
from config import Config
from utils import setup_logger

logger = setup_logger(__name__)

# File to store processed mention IDs
TRACKER_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'processed_mentions.json')


def _ensure_data_dir():
    """Ensure the data directory exists."""
    data_dir = os.path.dirname(TRACKER_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        logger.info(f"Created data directory: {data_dir}")


def make_dedup_key(mention: Dict[str, Any]) -> str:
    """Build a composite dedup key from a mention dict.

    The key is "{story_gid}:{user_gid}" so that a single comment mentioning
    both Jack and Deuce produces two independent keys. This prevents
    processing one user's mention from marking the other's as done.

    Args:
        mention: Mention dictionary with 'mention_story_gid' and 'mentioned_user_gid'

    Returns:
        Composite key string, or empty string if fields are missing
    """
    story_gid = mention.get('mention_story_gid', '')
    user_gid = mention.get('mentioned_user_gid', '')
    if not story_gid:
        return ''
    if not user_gid:
        # Fallback: use story_gid alone (legacy behavior, but log a warning)
        logger.warning(f"Mention missing 'mentioned_user_gid' — using story_gid only: {story_gid}")
        return story_gid
    return f"{story_gid}:{user_gid}"


def load_processed_mentions() -> Dict[str, Any]:
    """Load the set of already-processed mention keys.

    Keys are composite "{story_gid}:{user_gid}" strings.
    Legacy plain story_gid entries are preserved for backward compat
    but will NOT match new composite keys, ensuring they are re-processed
    per-user (which is the correct behavior for the migration).

    Returns:
        Dictionary with 'processed_ids' set and metadata
    """
    _ensure_data_dir()

    if not os.path.exists(TRACKER_FILE):
        return {
            'processed_ids': set(),
            'last_updated': None,
            'total_processed': 0
        }

    try:
        with open(TRACKER_FILE, 'r') as f:
            data = json.load(f)
            raw_ids = data.get('processed_ids', [])
            # Convert list back to set
            data['processed_ids'] = set(raw_ids)
            return data
    except Exception as e:
        logger.error(f"Error loading processed mentions: {e}")
        return {
            'processed_ids': set(),
            'last_updated': None,
            'total_processed': 0
        }


def save_processed_mentions(mention_ids: Set[str], existing_data: Dict[str, Any] = None):
    """Save newly processed mention IDs to the tracker file.

    Args:
        mention_ids: Set of composite dedup keys that were just processed
        existing_data: Existing tracker data to merge with
    """
    _ensure_data_dir()

    if existing_data is None:
        existing_data = load_processed_mentions()

    # Merge new IDs with existing
    all_ids = existing_data['processed_ids'] | mention_ids

    data = {
        'processed_ids': list(all_ids),  # Convert set to list for JSON
        'last_updated': datetime.now(Config.TIMEZONE).isoformat(),
        'total_processed': len(all_ids)
    }

    try:
        with open(TRACKER_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(mention_ids)} new processed mentions (total: {len(all_ids)})")
    except Exception as e:
        logger.error(f"Error saving processed mentions: {e}")


def filter_new_mentions(mentions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out mentions that have already been processed.

    Uses composite key "{story_gid}:{user_gid}" so that the same comment
    mentioning two users is tracked independently per user.

    Args:
        mentions: List of mention dictionaries

    Returns:
        List of mentions that haven't been processed yet
    """
    tracker_data = load_processed_mentions()
    processed_ids = tracker_data['processed_ids']

    new_mentions = []
    for mention in mentions:
        dedup_key = make_dedup_key(mention)
        if not dedup_key:
            # No story GID at all — include it (shouldn't happen, but safe)
            new_mentions.append(mention)
            continue
        if dedup_key not in processed_ids:
            new_mentions.append(mention)
        else:
            logger.debug(f"Skipping already-processed mention: {dedup_key}")

    if len(mentions) != len(new_mentions):
        logger.info(f"Filtered {len(mentions) - len(new_mentions)} already-processed mentions")

    return new_mentions


def mark_mentions_as_processed(mentions: List[Dict[str, Any]]):
    """Mark a list of mentions as processed using composite keys.

    Args:
        mentions: List of mention dictionaries
    """
    dedup_keys = set()
    for m in mentions:
        key = make_dedup_key(m)
        if key:
            dedup_keys.add(key)
    if dedup_keys:
        save_processed_mentions(dedup_keys)


def reserve_mentions(mentions: List[Dict[str, Any]]) -> Set[str]:
    """Atomically reserve mentions before creating Asana tasks.

    This prevents TOCTOU race conditions: if two runs overlap, the second
    run will see the mentions as already reserved and skip them.

    Args:
        mentions: List of mention dictionaries to reserve

    Returns:
        Set of dedup keys that were successfully reserved (not already taken)
    """
    tracker_data = load_processed_mentions()
    processed_ids = tracker_data['processed_ids']

    newly_reserved = set()
    for m in mentions:
        key = make_dedup_key(m)
        if key and key not in processed_ids:
            newly_reserved.add(key)

    if newly_reserved:
        # Write reservation immediately — before creating Asana tasks
        save_processed_mentions(newly_reserved, tracker_data)
        logger.info(f"Reserved {len(newly_reserved)} mentions for processing")

    return newly_reserved


def unreserve_mentions(dedup_keys: Set[str]):
    """Remove reservations for mentions that failed to create tasks.

    Called when Asana task creation fails, so the mentions can be retried
    on the next run.

    Args:
        dedup_keys: Set of composite keys to unreserve
    """
    if not dedup_keys:
        return

    tracker_data = load_processed_mentions()
    tracker_data['processed_ids'] -= dedup_keys

    data = {
        'processed_ids': list(tracker_data['processed_ids']),
        'last_updated': datetime.now(Config.TIMEZONE).isoformat(),
        'total_processed': len(tracker_data['processed_ids'])
    }

    try:
        with open(TRACKER_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Unreserved {len(dedup_keys)} mentions after failure")
    except Exception as e:
        logger.error(f"Error unreserving mentions: {e}")


def clear_old_processed_mentions(days_to_keep: int = 30):
    """Clear mentions older than specified days to prevent file bloat.

    Note: This is a simple implementation that clears all if file is too old.
    A more sophisticated version could track timestamps per mention.

    Args:
        days_to_keep: Number of days of data to retain
    """
    # For now, we keep all processed mentions indefinitely
    # This could be enhanced to track timestamps and prune old entries
    pass
