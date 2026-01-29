"""
Database operations for channel discovery.
"""

from datetime import datetime, timezone
from typing import Optional
from loguru import logger

from src.database.connection import get_client


# Default discovery settings
DEFAULT_SETTINGS = {
    "min_subscribers": 10000,
    "max_subscribers": 5000000,
    "min_videos": 20,
    "min_channel_age_days": 180,
    "exclude_kids_content": True,
    "country_filter": None,
    "activity_check": False,
    "max_days_since_upload": 60,
}


def get_discovery_settings(bucket_id: str) -> dict:
    """
    Get discovery settings for a bucket.
    Returns defaults if no custom settings exist.
    """
    client = get_client()

    try:
        result = client.table("bucket_discovery_settings").select("*").eq(
            "bucket_id", bucket_id
        ).execute()

        if result.data:
            settings = result.data[0]
            # Remove bucket_id and updated_at from settings dict
            return {
                "min_subscribers": settings["min_subscribers"],
                "max_subscribers": settings["max_subscribers"],
                "min_videos": settings["min_videos"],
                "min_channel_age_days": settings["min_channel_age_days"],
                "exclude_kids_content": settings["exclude_kids_content"],
                "country_filter": settings["country_filter"],
                "activity_check": settings["activity_check"],
                "max_days_since_upload": settings["max_days_since_upload"],
            }

        return DEFAULT_SETTINGS.copy()

    except Exception as e:
        logger.error(f"Error getting discovery settings: {e}")
        return DEFAULT_SETTINGS.copy()


def save_discovery_settings(bucket_id: str, settings: dict) -> bool:
    """
    Save discovery settings for a bucket.
    """
    client = get_client()

    try:
        data = {
            "bucket_id": bucket_id,
            "min_subscribers": settings.get("min_subscribers", DEFAULT_SETTINGS["min_subscribers"]),
            "max_subscribers": settings.get("max_subscribers", DEFAULT_SETTINGS["max_subscribers"]),
            "min_videos": settings.get("min_videos", DEFAULT_SETTINGS["min_videos"]),
            "min_channel_age_days": settings.get("min_channel_age_days", DEFAULT_SETTINGS["min_channel_age_days"]),
            "exclude_kids_content": settings.get("exclude_kids_content", DEFAULT_SETTINGS["exclude_kids_content"]),
            "country_filter": settings.get("country_filter", DEFAULT_SETTINGS["country_filter"]),
            "activity_check": settings.get("activity_check", DEFAULT_SETTINGS["activity_check"]),
            "max_days_since_upload": settings.get("max_days_since_upload", DEFAULT_SETTINGS["max_days_since_upload"]),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        client.table("bucket_discovery_settings").upsert(data).execute()
        logger.info(f"Saved discovery settings for bucket {bucket_id}")
        return True

    except Exception as e:
        logger.error(f"Error saving discovery settings: {e}")
        return False


def get_tracked_channel_ids() -> set[str]:
    """
    Get all channel IDs currently being tracked.
    Used to filter out channels we already have.
    """
    client = get_client()

    try:
        result = client.table("channels").select("channel_id").execute()
        return {row["channel_id"] for row in result.data}

    except Exception as e:
        logger.error(f"Error getting tracked channels: {e}")
        return set()


def get_suggested_channel_ids(bucket_id: str) -> set[str]:
    """
    Get channel IDs that have already been suggested for this bucket.
    Includes pending, accepted, and declined to avoid re-suggesting.
    """
    client = get_client()

    try:
        result = client.table("channel_suggestions").select("channel_id").eq(
            "bucket_id", bucket_id
        ).execute()
        return {row["channel_id"] for row in result.data}

    except Exception as e:
        logger.error(f"Error getting suggested channels: {e}")
        return set()


def save_channel_suggestions(bucket_id: str, suggestions: list[dict]) -> int:
    """
    Save channel suggestions to the database.

    Args:
        bucket_id: Bucket ID
        suggestions: List of channel dicts with:
            channel_id, channel_name, subscriber_count, video_count,
            published_at, thumbnail_url, country, matched_keywords

    Returns:
        Number of suggestions saved.
    """
    if not suggestions:
        return 0

    client = get_client()
    saved = 0

    for suggestion in suggestions:
        try:
            data = {
                "bucket_id": bucket_id,
                "channel_id": suggestion["channel_id"],
                "channel_name": suggestion["channel_name"],
                "subscriber_count": suggestion.get("subscriber_count"),
                "video_count": suggestion.get("video_count"),
                "channel_created_at": suggestion.get("published_at"),
                "thumbnail_url": suggestion.get("thumbnail_url"),
                "country": suggestion.get("country"),
                "matched_keywords": suggestion.get("matched_keywords", []),
                "status": "pending",
            }

            client.table("channel_suggestions").upsert(
                data,
                on_conflict="bucket_id,channel_id"
            ).execute()
            saved += 1

        except Exception as e:
            logger.error(f"Error saving suggestion {suggestion.get('channel_id')}: {e}")

    logger.info(f"Saved {saved} channel suggestions for bucket {bucket_id}")
    return saved


def get_pending_suggestions(bucket_id: str) -> list[dict]:
    """
    Get pending channel suggestions for a bucket.
    """
    client = get_client()

    try:
        result = client.table("channel_suggestions").select("*").eq(
            "bucket_id", bucket_id
        ).eq(
            "status", "pending"
        ).order("suggested_at", desc=True).execute()

        return result.data

    except Exception as e:
        logger.error(f"Error getting pending suggestions: {e}")
        return []


def get_all_suggestions(bucket_id: str) -> list[dict]:
    """
    Get all channel suggestions for a bucket (any status).
    """
    client = get_client()

    try:
        result = client.table("channel_suggestions").select("*").eq(
            "bucket_id", bucket_id
        ).order("suggested_at", desc=True).execute()

        return result.data

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        return []


def update_suggestion_status(suggestion_id: int, status: str) -> bool:
    """
    Update the status of a channel suggestion.

    Args:
        suggestion_id: Suggestion ID
        status: 'accepted' or 'declined'
    """
    if status not in ('accepted', 'declined'):
        logger.error(f"Invalid suggestion status: {status}")
        return False

    client = get_client()

    try:
        client.table("channel_suggestions").update({
            "status": status,
            "responded_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", suggestion_id).execute()

        logger.info(f"Updated suggestion {suggestion_id} to {status}")
        return True

    except Exception as e:
        logger.error(f"Error updating suggestion status: {e}")
        return False


def accept_suggestion(suggestion_id: int) -> Optional[dict]:
    """
    Accept a channel suggestion and return the channel info.
    The caller is responsible for adding the channel to tracking.

    Returns:
        Channel info dict if successful, None otherwise.
    """
    client = get_client()

    try:
        # Get the suggestion
        result = client.table("channel_suggestions").select("*").eq(
            "id", suggestion_id
        ).single().execute()

        if not result.data:
            logger.error(f"Suggestion {suggestion_id} not found")
            return None

        suggestion = result.data

        # Update status
        update_suggestion_status(suggestion_id, "accepted")

        return {
            "channel_id": suggestion["channel_id"],
            "channel_name": suggestion["channel_name"],
            "subscriber_count": suggestion["subscriber_count"],
            "video_count": suggestion["video_count"],
            "bucket_id": suggestion["bucket_id"],
        }

    except Exception as e:
        logger.error(f"Error accepting suggestion: {e}")
        return None


def decline_suggestion(suggestion_id: int) -> bool:
    """
    Decline a channel suggestion.
    """
    return update_suggestion_status(suggestion_id, "declined")


def clear_pending_suggestions(bucket_id: str) -> int:
    """
    Clear all pending suggestions for a bucket.
    Useful before running a new discovery.
    """
    client = get_client()

    try:
        result = client.table("channel_suggestions").delete().eq(
            "bucket_id", bucket_id
        ).eq(
            "status", "pending"
        ).execute()

        count = len(result.data) if result.data else 0
        if count > 0:
            logger.info(f"Cleared {count} pending suggestions for bucket {bucket_id}")
        return count

    except Exception as e:
        logger.error(f"Error clearing suggestions: {e}")
        return 0
