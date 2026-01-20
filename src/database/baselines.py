"""
Baseline calculation and storage.

Baselines are calculated from ANY video that has a snapshot at that window,
not just completed videos. This allows baselines to be available much sooner:
- 1h baseline: available after 1 hour (with enough videos)
- 24h baseline: available after 24 hours
- etc.
"""

import statistics
from datetime import datetime
from .connection import get_client
from src.config import Config


def calculate_median(values: list[int]) -> int | None:
    """Calculate median of a list of integers."""
    if not values:
        return None
    return int(statistics.median(values))


def get_snapshots_for_baseline(channel_id: str, is_short: bool, window_type: str, limit: int = None) -> list[dict]:
    """
    Get snapshots at a specific window for a channel's videos.

    This joins videos and snapshots to get all snapshots at a window
    for videos matching the channel and content type (short/long).

    Does NOT require videos to be 'completed' - any video with a snapshot
    at this window is included.
    """
    client = get_client()

    if limit is None:
        limit = Config.BASELINE_SAMPLE_SIZE

    # Query snapshots joined with videos
    # We need videos that: belong to this channel, match is_short, and have a snapshot at this window
    result = (
        client.table("snapshots")
        .select("*, videos!inner(channel_id, is_short, published_at)")
        .eq("videos.channel_id", channel_id)
        .eq("videos.is_short", is_short)
        .eq("window_type", window_type)
        .order("captured_at", desc=True)
        .limit(limit)
        .execute()
    )

    return result.data


def calculate_channel_baseline(channel_id: str, is_short: bool, window_type: str) -> dict | None:
    """
    Calculate baseline for a channel at a specific window.

    Args:
        channel_id: The YouTube channel ID
        is_short: True for Shorts, False for Long-form
        window_type: One of '1h', '6h', '24h', '48h'

    Returns:
        Dict with median_views, median_likes, median_comments, sample_size
        or None if not enough data.

    Note: Uses ANY video with a snapshot at this window, not just completed videos.
    This means baselines are available much sooner (after window time + min samples).
    """
    # Get snapshots at this window for this channel and content type
    snapshots = get_snapshots_for_baseline(channel_id, is_short, window_type)

    if len(snapshots) < Config.BASELINE_MIN_SAMPLE:
        return None  # Not enough data yet

    # Extract values
    views = [s["views"] for s in snapshots]
    likes = [s["likes"] for s in snapshots]
    comments = [s["comments"] for s in snapshots]

    return {
        "median_views": calculate_median(views),
        "median_likes": calculate_median(likes),
        "median_comments": calculate_median(comments),
        "sample_size": len(snapshots),
    }


def update_channel_baseline(channel_id: str, is_short: bool, window_type: str) -> dict | None:
    """
    Calculate and store/update baseline for a channel.
    Uses upsert to insert or update.
    """
    baseline = calculate_channel_baseline(channel_id, is_short, window_type)

    if baseline is None:
        return None

    client = get_client()

    data = {
        "channel_id": channel_id,
        "is_short": is_short,
        "window_type": window_type,
        "median_views": baseline["median_views"],
        "median_likes": baseline["median_likes"],
        "median_comments": baseline["median_comments"],
        "sample_size": baseline["sample_size"],
        "updated_at": datetime.utcnow().isoformat(),
    }

    # Upsert: insert if not exists, update if exists
    result = (
        client.table("channel_baselines")
        .upsert(data, on_conflict="channel_id,is_short,window_type")
        .execute()
    )

    return result.data[0] if result.data else None


def update_all_baselines_for_channel(channel_id: str) -> dict:
    """
    Update all baselines for a channel (both Shorts and Long, all windows).
    Returns summary of what was updated.
    """
    windows = ["1h", "6h", "24h", "48h"]
    results = {
        "channel_id": channel_id,
        "updated": [],
        "skipped": [],
    }

    for is_short in [True, False]:
        content_type = "short" if is_short else "long"
        for window in windows:
            baseline = update_channel_baseline(channel_id, is_short, window)
            if baseline:
                results["updated"].append(f"{content_type}_{window}")
            else:
                results["skipped"].append(f"{content_type}_{window}")

    return results


def get_channel_baseline(channel_id: str, is_short: bool, window_type: str) -> dict | None:
    """Get stored baseline for a channel."""
    client = get_client()

    result = (
        client.table("channel_baselines")
        .select("*")
        .eq("channel_id", channel_id)
        .eq("is_short", is_short)
        .eq("window_type", window_type)
        .execute()
    )

    return result.data[0] if result.data else None


def get_all_channel_baselines(channel_id: str) -> list[dict]:
    """Get all baselines for a channel."""
    client = get_client()

    result = (
        client.table("channel_baselines")
        .select("*")
        .eq("channel_id", channel_id)
        .execute()
    )

    return result.data
