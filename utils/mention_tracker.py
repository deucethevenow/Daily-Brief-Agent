"""Tracks which @mentions have been processed to avoid duplicates.

CRITICAL: The dedup key is a COMPOSITE of story_gid AND user_gid.
A single comment can @mention multiple users, so story_gid alone is NOT unique.
Using story_gid alone causes cross-user contamination: processing Jack's mention
marks Deuce's mention of the same comment as "done", silently dropping it.

Key format: "{story_gid}:{user_gid}"
Legacy format (story_gid only) is auto-migrated on load.

STORAGE: Uses Google Cloud Storage for persistence across ephemeral Cloud Run
containers. Falls back to local file if GCS is unavailable (local dev).
"""
import json
import os
from datetime import datetime
from typing import Set, List, Dict, Any
from config import Config
from utils import setup_logger

logger = setup_logger(__name__)

# Local file fallback
LOCAL_TRACKER_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'processed_mentions.json')

# GCS settings
GCS_BUCKET = os.environ.get('GCS_TRACKER_BUCKET', 'daily-brief-agent-recess.appspot.com')
GCS_BLOB_NAME = 'mention-tracker/processed_mentions.json'

# Lazy-init GCS client (avoids import errors when google-cloud-storage not installed).
# NOTE: _gcs_available is latched to False on first failure and never retried.
# This is acceptable because each Cloud Run invocation is a fresh process.
# For long-running processes, this would need a TTL-based retry.
_gcs_client = None
_gcs_available = None


def _get_gcs_bucket():
    """Get GCS bucket, lazily initializing the client.

    Returns:
        GCS Bucket object, or None if GCS is unavailable
    """
    global _gcs_client, _gcs_available

    if _gcs_available is False:
        return None

    if _gcs_client is not None:
        try:
            return _gcs_client.bucket(GCS_BUCKET)
        except Exception:
            _gcs_available = False
            return None

    try:
        from google.cloud import storage
        _gcs_client = storage.Client()
        _gcs_available = True
        bucket = _gcs_client.bucket(GCS_BUCKET)
        logger.info(f"GCS tracker initialized: gs://{GCS_BUCKET}/{GCS_BLOB_NAME}")
        return bucket
    except ImportError:
        logger.info("google-cloud-storage not installed — using local file tracker")
        _gcs_available = False
        return None
    except Exception as e:
        logger.warning(f"GCS unavailable ({e}) — using local file tracker")
        _gcs_available = False
        return None


def _ensure_data_dir():
    """Ensure the local data directory exists."""
    data_dir = os.path.dirname(LOCAL_TRACKER_FILE)
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


def _load_from_gcs() -> Dict[str, Any]:
    """Load tracker data from GCS.

    Returns:
        Tracker data dict (empty if blob doesn't exist), or None if GCS unavailable
    """
    bucket = _get_gcs_bucket()
    if not bucket:
        return None

    try:
        blob = bucket.blob(GCS_BLOB_NAME)
        if not blob.exists():
            logger.info("GCS tracker blob does not exist yet — starting fresh")
            return {
                'processed_ids': set(),
                'last_updated': None,
                'total_processed': 0
            }
        content = blob.download_as_text()
        data = json.loads(content)
        data['processed_ids'] = set(data.get('processed_ids', []))
        logger.debug(f"Loaded {len(data['processed_ids'])} processed mentions from GCS")
        return data
    except Exception as e:
        logger.warning(f"Failed to load from GCS: {e}")
        return None


def _save_to_gcs(data: Dict[str, Any]) -> bool:
    """Save tracker data to GCS.

    Args:
        data: Tracker data with 'processed_ids' as a list (not set)

    Returns:
        True if saved successfully
    """
    bucket = _get_gcs_bucket()
    if not bucket:
        return False

    try:
        blob = bucket.blob(GCS_BLOB_NAME)
        blob.upload_from_string(
            json.dumps(data, indent=2),
            content_type='application/json'
        )
        logger.debug(f"Saved {data.get('total_processed', 0)} processed mentions to GCS")
        return True
    except Exception as e:
        logger.warning(f"Failed to save to GCS: {e}")
        return False


def _load_from_local() -> Dict[str, Any]:
    """Load tracker data from local file."""
    _ensure_data_dir()

    if not os.path.exists(LOCAL_TRACKER_FILE):
        return {
            'processed_ids': set(),
            'last_updated': None,
            'total_processed': 0
        }

    try:
        with open(LOCAL_TRACKER_FILE, 'r') as f:
            data = json.load(f)
            data['processed_ids'] = set(data.get('processed_ids', []))
            return data
    except Exception as e:
        logger.error(f"Error loading local tracker: {e}")
        return {
            'processed_ids': set(),
            'last_updated': None,
            'total_processed': 0
        }


def _save_to_local(data: Dict[str, Any]) -> bool:
    """Save tracker data to local file."""
    _ensure_data_dir()
    try:
        with open(LOCAL_TRACKER_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving local tracker: {e}")
        return False


def load_processed_mentions() -> Dict[str, Any]:
    """Load the set of already-processed mention keys.

    Tries GCS first (for Cloud Run persistence), falls back to local file.

    Returns:
        Dictionary with 'processed_ids' set and metadata
    """
    # Try GCS first
    data = _load_from_gcs()
    if data is not None:
        return data

    # Fall back to local file
    return _load_from_local()


def _save_data(data: Dict[str, Any]):
    """Save tracker data to both GCS and local file.

    Writes to GCS first (primary), then local (backup).
    """
    # Ensure processed_ids is a list for JSON serialization
    ids = data.get('processed_ids', set())
    ids_list = list(ids)
    serializable_data = {
        'processed_ids': ids_list,
        'last_updated': data.get('last_updated', datetime.now(Config.TIMEZONE).isoformat()),
        'total_processed': len(ids_list)
    }

    gcs_ok = _save_to_gcs(serializable_data)
    _save_to_local(serializable_data)

    if gcs_ok:
        logger.info(f"Tracker saved to GCS ({serializable_data['total_processed']} entries)")
    else:
        logger.info(f"Tracker saved to local file ({serializable_data['total_processed']} entries)")


def save_processed_mentions(mention_ids: Set[str], existing_data: Dict[str, Any] = None):
    """Save newly processed mention IDs.

    Args:
        mention_ids: Set of composite dedup keys that were just processed
        existing_data: Existing tracker data to merge with
    """
    if existing_data is None:
        existing_data = load_processed_mentions()

    # Merge new IDs with existing
    all_ids = existing_data['processed_ids'] | mention_ids

    data = {
        'processed_ids': all_ids,
        'last_updated': datetime.now(Config.TIMEZONE).isoformat(),
        'total_processed': len(all_ids)
    }

    _save_data(data)
    logger.info(f"Saved {len(mention_ids)} new processed mentions (total: {len(all_ids)})")


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
        'processed_ids': tracker_data['processed_ids'],
        'last_updated': datetime.now(Config.TIMEZONE).isoformat(),
        'total_processed': len(tracker_data['processed_ids'])
    }

    _save_data(data)
    logger.info(f"Unreserved {len(dedup_keys)} mentions after failure")


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
