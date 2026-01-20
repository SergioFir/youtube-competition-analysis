"""
Snapshot database operations.
"""

from datetime import datetime
from .connection import get_client
from src.config import Config


def add_snapshot(
    video_id: str,
    window_type: str,
    views: int,
    likes: int,
    comments: int,
) -> dict:
    """
    Add a snapshot for a video.
    Returns the inserted snapshot data.
    """
    client = get_client()

    data = {
        "video_id": video_id,
        "window_type": window_type,
        "views": views,
        "likes": likes,
        "comments": comments,
        # captured_at defaults to NOW() in database
    }

    result = client.table("snapshots").insert(data).execute()
    return result.data[0] if result.data else None


def get_video_snapshots(video_id: str) -> list[dict]:
    """Get all snapshots for a video, ordered by window."""
    client = get_client()

    result = (
        client.table("snapshots")
        .select("*")
        .eq("video_id", video_id)
        .order("captured_at")
        .execute()
    )
    return result.data


def get_snapshot_by_window(video_id: str, window_type: str) -> dict | None:
    """Get a specific snapshot for a video by window type."""
    client = get_client()

    result = (
        client.table("snapshots")
        .select("*")
        .eq("video_id", video_id)
        .eq("window_type", window_type)
        .execute()
    )
    return result.data[0] if result.data else None


def get_pending_scheduled_snapshots(limit: int = 100) -> list[dict]:
    """
    Get scheduled snapshots that are due to be taken.
    Returns snapshots where scheduled_for <= NOW() and status = 'pending'.
    """
    client = get_client()

    now = datetime.utcnow().isoformat()

    result = (
        client.table("scheduled_snapshots")
        .select("*, videos(*)")  # Join with videos table
        .eq("status", "pending")
        .lte("scheduled_for", now)
        .order("scheduled_for")
        .limit(limit)
        .execute()
    )
    return result.data


def mark_scheduled_snapshot_completed(scheduled_id: int) -> dict | None:
    """Mark a scheduled snapshot as completed."""
    client = get_client()

    result = (
        client.table("scheduled_snapshots")
        .update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
        })
        .eq("id", scheduled_id)
        .execute()
    )
    return result.data[0] if result.data else None


def mark_scheduled_snapshot_failed(scheduled_id: int, error: str) -> dict | None:
    """Mark a scheduled snapshot as failed, incrementing attempt count."""
    client = get_client()

    # First get current attempts
    current = client.table("scheduled_snapshots").select("attempts").eq("id", scheduled_id).execute()
    current_attempts = current.data[0]["attempts"] if current.data else 0

    new_attempts = current_attempts + 1
    new_status = "failed" if new_attempts >= Config.MAX_SNAPSHOT_ATTEMPTS else "pending"

    result = (
        client.table("scheduled_snapshots")
        .update({
            "status": new_status,
            "attempts": new_attempts,
            "last_error": error,
        })
        .eq("id", scheduled_id)
        .execute()
    )
    return result.data[0] if result.data else None


def get_snapshot_coverage(video_id: str) -> dict:
    """
    Calculate snapshot coverage for a video.
    Returns dict with actual, expected, and coverage ratio.
    """
    client = get_client()

    result = client.table("snapshots").select("id").eq("video_id", video_id).execute()
    actual = len(result.data)
    expected = len(Config.SNAPSHOT_WINDOWS)  # 8 windows

    return {
        "video_id": video_id,
        "actual": actual,
        "expected": expected,
        "coverage": actual / expected if expected > 0 else 0,
    }


def get_videos_snapshots_at_window(video_ids: list[str], window_type: str) -> list[dict]:
    """
    Get snapshots for multiple videos at a specific window.
    Used for baseline calculation.
    """
    client = get_client()

    result = (
        client.table("snapshots")
        .select("*")
        .in_("video_id", video_ids)
        .eq("window_type", window_type)
        .execute()
    )
    return result.data
