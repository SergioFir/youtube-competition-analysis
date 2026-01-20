"""
Video database operations.
"""

from datetime import datetime, timedelta
from .connection import get_client
from src.config import Config


def add_video(
    video_id: str,
    channel_id: str,
    published_at: datetime,
    title: str = None,
    duration_seconds: int = None,
    is_short: bool = None,
) -> dict:
    """
    Add a new video and create its scheduled snapshots.
    Returns the inserted video data.
    """
    client = get_client()

    data = {
        "video_id": video_id,
        "channel_id": channel_id,
        "published_at": published_at.isoformat(),
        "title": title,
        "duration_seconds": duration_seconds,
        "is_short": is_short,
        "tracking_status": "active",
        # tracking_until is auto-set by database trigger
    }

    result = client.table("videos").insert(data).execute()
    video = result.data[0] if result.data else None

    if video:
        # Create scheduled snapshots for all windows (except 0h which we take immediately)
        _create_scheduled_snapshots(video_id, published_at)

    return video


def _create_scheduled_snapshots(video_id: str, published_at: datetime) -> None:
    """Create scheduled snapshot entries for a video."""
    client = get_client()

    schedules = []
    for window_type, hours in Config.SNAPSHOT_WINDOWS.items():
        if window_type == "0h":
            continue  # T+0 is taken immediately, not scheduled

        scheduled_for = published_at + timedelta(hours=hours)
        schedules.append({
            "video_id": video_id,
            "window_type": window_type,
            "scheduled_for": scheduled_for.isoformat(),
            "status": "pending",
        })

    if schedules:
        client.table("scheduled_snapshots").insert(schedules).execute()


def get_video(video_id: str) -> dict | None:
    """Get a video by ID."""
    client = get_client()

    result = client.table("videos").select("*").eq("video_id", video_id).execute()
    return result.data[0] if result.data else None


def video_exists(video_id: str) -> bool:
    """Check if a video already exists in the database."""
    return get_video(video_id) is not None


def get_active_videos() -> list[dict]:
    """Get all videos with tracking_status = 'active'."""
    client = get_client()

    result = client.table("videos").select("*").eq("tracking_status", "active").execute()
    return result.data


def get_channel_videos(channel_id: str, status: str = None, limit: int = 50) -> list[dict]:
    """
    Get videos for a channel.
    Optionally filter by tracking_status.
    """
    client = get_client()

    query = client.table("videos").select("*").eq("channel_id", channel_id)
    if status:
        query = query.eq("tracking_status", status)

    result = query.order("published_at", desc=True).limit(limit).execute()
    return result.data


def update_video(video_id: str, **kwargs) -> dict | None:
    """Update a video's fields."""
    client = get_client()

    result = client.table("videos").update(kwargs).eq("video_id", video_id).execute()
    return result.data[0] if result.data else None


def mark_video_completed(video_id: str) -> dict | None:
    """Mark a video as completed (tracking finished)."""
    return update_video(video_id, tracking_status="completed")


def mark_video_deleted(video_id: str) -> dict | None:
    """Mark a video as deleted (removed from YouTube)."""
    return update_video(video_id, tracking_status="deleted")


def get_completed_videos_for_baseline(channel_id: str, is_short: bool, limit: int = None) -> list[dict]:
    """
    Get completed videos for baseline calculation.
    Filters by channel and content type (short vs long).
    """
    client = get_client()

    if limit is None:
        limit = Config.BASELINE_SAMPLE_SIZE

    query = (
        client.table("videos")
        .select("*")
        .eq("channel_id", channel_id)
        .eq("tracking_status", "completed")
        .eq("is_short", is_short)
        .order("published_at", desc=True)
        .limit(limit)
    )

    result = query.execute()
    return result.data
