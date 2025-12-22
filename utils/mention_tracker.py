"""Tracks which @mentions have been processed to avoid duplicates."""
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


def load_processed_mentions() -> Dict[str, Any]:
    """Load the set of already-processed mention story GIDs.

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
            # Convert list back to set
            data['processed_ids'] = set(data.get('processed_ids', []))
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
        mention_ids: Set of mention story GIDs that were just processed
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

    Args:
        mentions: List of mention dictionaries with 'mention_story_gid' field

    Returns:
        List of mentions that haven't been processed yet
    """
    tracker_data = load_processed_mentions()
    processed_ids = tracker_data['processed_ids']

    new_mentions = []
    for mention in mentions:
        story_gid = mention.get('mention_story_gid')
        if story_gid and story_gid not in processed_ids:
            new_mentions.append(mention)
        elif story_gid in processed_ids:
            logger.debug(f"Skipping already-processed mention: {story_gid}")

    if len(mentions) != len(new_mentions):
        logger.info(f"Filtered {len(mentions) - len(new_mentions)} already-processed mentions")

    return new_mentions


def mark_mentions_as_processed(mentions: List[Dict[str, Any]]):
    """Mark a list of mentions as processed.

    Args:
        mentions: List of mention dictionaries with 'mention_story_gid' field
    """
    mention_ids = {m.get('mention_story_gid') for m in mentions if m.get('mention_story_gid')}
    if mention_ids:
        save_processed_mentions(mention_ids)


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
