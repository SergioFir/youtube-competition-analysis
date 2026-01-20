"""
Channel database operations.
"""

from datetime import datetime
from .connection import get_client


def add_channel(channel_id: str, channel_name: str, subscriber_count: int = None, total_videos: int = None) -> dict:
    """
    Add a new channel to track.
    Returns the inserted channel data.
    """
    client = get_client()

    data = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "subscriber_count": subscriber_count,
        "total_videos": total_videos,
        "is_active": True,
    }

    result = client.table("channels").insert(data).execute()
    return result.data[0] if result.data else None


def get_channel(channel_id: str) -> dict | None:
    """Get a channel by ID."""
    client = get_client()

    result = client.table("channels").select("*").eq("channel_id", channel_id).execute()
    return result.data[0] if result.data else None


def get_active_channels() -> list[dict]:
    """Get all active channels (is_active = True)."""
    client = get_client()

    result = client.table("channels").select("*").eq("is_active", True).execute()
    return result.data


def update_channel(channel_id: str, **kwargs) -> dict | None:
    """
    Update a channel's fields.
    Pass any fields to update as keyword arguments.
    """
    client = get_client()

    kwargs["last_checked_at"] = datetime.utcnow().isoformat()

    result = client.table("channels").update(kwargs).eq("channel_id", channel_id).execute()
    return result.data[0] if result.data else None


def deactivate_channel(channel_id: str) -> dict | None:
    """Mark a channel as inactive (stop tracking)."""
    return update_channel(channel_id, is_active=False)


def list_channels(active_only: bool = True) -> list[dict]:
    """List all channels, optionally filtering by active status."""
    client = get_client()

    query = client.table("channels").select("*")
    if active_only:
        query = query.eq("is_active", True)

    result = query.order("created_at", desc=True).execute()
    return result.data
