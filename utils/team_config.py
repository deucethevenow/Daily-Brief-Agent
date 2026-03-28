"""Team configuration for monitored users.

Loads user config from GCS (primary) with env var fallback.
Allows adding/removing users without redeploying — just edit the
JSON file in GCS.

Config location: gs://{GCS_BUCKET}/config/monitored_users.json
"""
import json
import os
from typing import List, Dict, Any, Optional
from utils import setup_logger

logger = setup_logger(__name__)

GCS_BUCKET = os.environ.get('GCS_TRACKER_BUCKET', 'daily-brief-agent-recess.appspot.com')
GCS_CONFIG_BLOB = 'config/monitored_users.json'

# Cache to avoid re-fetching within the same run
_cached_config = None


def _load_from_gcs() -> Optional[Dict[str, Any]]:
    """Load team config from GCS."""
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(GCS_CONFIG_BLOB)

        if not blob.exists():
            logger.info(f"No team config in GCS at gs://{GCS_BUCKET}/{GCS_CONFIG_BLOB}")
            return None

        content = blob.download_as_text()
        config = json.loads(content)
        logger.info(f"Loaded team config from GCS: {len(config.get('monitored_users', []))} users")
        return config
    except ImportError:
        logger.info("google-cloud-storage not installed — using env var fallback")
        return None
    except Exception as e:
        logger.warning(f"Failed to load team config from GCS: {e}")
        return None


def _load_from_env() -> Dict[str, Any]:
    """Build config from MONITORED_USERS env var (fallback)."""
    from config import Config
    users = []
    for name in Config.MONITORED_USER_NAMES:
        users.append({
            'name': name,
            'enabled': True,
            'slack_user_id': None,  # Unknown without Slack lookup
        })
    logger.info(f"Using env var fallback: {len(users)} monitored users")
    return {'monitored_users': users}


def get_team_config() -> Dict[str, Any]:
    """Get the full team configuration.

    Tries GCS first, falls back to MONITORED_USERS env var.
    Cached for the duration of the process.

    Returns:
        Dict with 'monitored_users' list
    """
    global _cached_config
    if _cached_config is not None:
        return _cached_config

    config = _load_from_gcs()
    if config is None:
        config = _load_from_env()

    _cached_config = config
    return config


def get_monitored_user_names() -> List[str]:
    """Get list of enabled monitored user names.

    Returns:
        List of user display names (Asana names)
    """
    config = get_team_config()
    names = [
        u['name'] for u in config.get('monitored_users', [])
        if u.get('enabled', True)
    ]
    logger.info(f"Monitoring {len(names)} users: {names}")
    return names


def get_user_slack_id(asana_name: str) -> Optional[str]:
    """Get a user's Slack user ID from their Asana name.

    Args:
        asana_name: The user's display name in Asana

    Returns:
        Slack user ID string (e.g., "U01ABC123") or None
    """
    config = get_team_config()
    for user in config.get('monitored_users', []):
        if user.get('name') == asana_name:
            return user.get('slack_user_id')
    return None


def get_all_user_slack_ids() -> Dict[str, str]:
    """Get a mapping of Asana name → Slack user ID for all enabled users.

    Returns:
        Dict mapping name to Slack user ID (excludes users without Slack ID)
    """
    config = get_team_config()
    mapping = {}
    for user in config.get('monitored_users', []):
        if user.get('enabled', True) and user.get('slack_user_id'):
            mapping[user['name']] = user['slack_user_id']
    return mapping


def save_config_to_gcs(config: Dict[str, Any]) -> bool:
    """Save team config to GCS.

    Args:
        config: Full config dict with 'monitored_users' list

    Returns:
        True if saved successfully
    """
    try:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob(GCS_CONFIG_BLOB)
        blob.upload_from_string(
            json.dumps(config, indent=2),
            content_type='application/json'
        )
        logger.info(f"Saved team config to GCS: {len(config.get('monitored_users', []))} users")
        return True
    except Exception as e:
        logger.error(f"Failed to save team config to GCS: {e}")
        return False
