"""
Database operations for topics and trends.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from loguru import logger

from src.config import Config
from src.database.connection import get_client


def add_video_topics(video_id: str, topics: list[str]) -> bool:
    """
    Add extracted topics for a video.

    Args:
        video_id: YouTube video ID
        topics: List of topic strings

    Returns:
        True if successful.
    """
    if not topics:
        return True

    client = get_client()

    try:
        # Insert all topics
        rows = [{"video_id": video_id, "topic": topic} for topic in topics]
        client.table("video_topics").insert(rows).execute()

        logger.debug(f"Added {len(topics)} topics for video {video_id}")
        return True
    except Exception as e:
        logger.error(f"Error adding topics for {video_id}: {e}")
        return False


def get_video_topics(video_id: str) -> list[str]:
    """Get topics for a video."""
    client = get_client()

    try:
        result = client.table("video_topics").select("topic").eq("video_id", video_id).execute()
        return [row["topic"] for row in result.data]
    except Exception as e:
        logger.error(f"Error getting topics for {video_id}: {e}")
        return []


def video_has_topics(video_id: str) -> bool:
    """Check if a video already has topics extracted."""
    client = get_client()

    try:
        result = client.table("video_topics").select("id").eq("video_id", video_id).limit(1).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Error checking topics for {video_id}: {e}")
        return False


def get_topics_for_bucket(
    channel_ids: list[str],
    days: int = None,
    min_performance: float = None,
) -> list[dict]:
    """
    Get topics from high-performing videos for specific channels (bucket).

    Args:
        channel_ids: List of channel IDs to include
        days: Number of days to look back (default: TREND_WINDOW_DAYS)
        min_performance: Minimum performance ratio (default: TREND_MIN_PERFORMANCE)

    Returns:
        List of dicts with video_id, channel_id, topic, performance_ratio.
    """
    if days is None:
        days = Config.TREND_WINDOW_DAYS
    if min_performance is None:
        min_performance = Config.TREND_MIN_PERFORMANCE

    if not channel_ids:
        return []

    client = get_client()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    return _get_topics_fallback(client, cutoff, min_performance, channel_ids)


def get_all_topics_for_trending(
    days: int = None,
    min_performance: float = None,
) -> list[dict]:
    """
    Get all topics from high-performing videos in the time window.
    (Legacy function - use get_topics_for_bucket for per-bucket detection)
    """
    if days is None:
        days = Config.TREND_WINDOW_DAYS
    if min_performance is None:
        min_performance = Config.TREND_MIN_PERFORMANCE

    client = get_client()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    return _get_topics_fallback(client, cutoff, min_performance)


def _get_topics_fallback(
    client,
    cutoff: datetime,
    min_performance: float,
    channel_ids: list[str] = None
) -> list[dict]:
    """Fallback method to get topics, optionally filtered by channels."""
    try:
        # Get all video topics
        topics_result = client.table("video_topics").select("video_id, topic").execute()
        topics_by_video = {}
        for row in topics_result.data:
            vid = row["video_id"]
            if vid not in topics_by_video:
                topics_by_video[vid] = []
            topics_by_video[vid].append(row["topic"])

        # Get videos with their performance
        query = client.table("videos").select(
            "video_id, channel_id, title, published_at, is_short"
        ).gte("published_at", cutoff.isoformat())

        # Filter by channels if specified
        if channel_ids:
            query = query.in_("channel_id", channel_ids)

        videos_result = query.execute()

        # Get 24h snapshots
        video_ids = [v["video_id"] for v in videos_result.data]
        if not video_ids:
            return []

        snapshots_result = client.table("snapshots").select(
            "video_id, views"
        ).eq("window_type", "24h").in_("video_id", video_ids).execute()
        snapshots = {s["video_id"]: s["views"] for s in snapshots_result.data}

        # Get baselines
        baselines_result = client.table("channel_baselines").select(
            "channel_id, is_short, median_views"
        ).eq("window_type", "24h").execute()
        baselines = {}
        for b in baselines_result.data:
            key = (b["channel_id"], b["is_short"])
            baselines[key] = b["median_views"]

        # Build result
        results = []
        for video in videos_result.data:
            vid = video["video_id"]
            if vid not in topics_by_video or vid not in snapshots:
                continue

            views = snapshots[vid]
            baseline = baselines.get((video["channel_id"], video["is_short"]), 0)

            if baseline > 0:
                performance = round(views / baseline, 2)
                if performance < min_performance:
                    continue
            else:
                performance = None

            for topic in topics_by_video[vid]:
                results.append({
                    "video_id": vid,
                    "channel_id": video["channel_id"],
                    "title": video["title"],
                    "topic": topic,
                    "views_24h": views,
                    "baseline_24h": baseline,
                    "performance_ratio": performance,
                })

        return results

    except Exception as e:
        logger.error(f"Fallback query failed: {e}")
        return []


def save_cluster(normalized_name: str, topics: list[str], bucket_id: str = None) -> Optional[str]:
    """
    Save a topic cluster to the database.

    Args:
        normalized_name: Normalized cluster name
        topics: List of raw topics in this cluster
        bucket_id: Optional bucket ID this cluster belongs to

    Returns:
        Cluster ID if successful.
    """
    client = get_client()

    try:
        # Check if cluster already exists for this bucket
        query = client.table("topic_clusters").select("id").eq(
            "normalized_name", normalized_name
        )
        if bucket_id:
            query = query.eq("bucket_id", bucket_id)
        else:
            query = query.is_("bucket_id", "null")

        existing = query.execute()

        if existing.data:
            cluster_id = existing.data[0]["id"]
            # Update timestamp
            client.table("topic_clusters").update({
                "updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", cluster_id).execute()
        else:
            # Create new cluster
            insert_data = {"normalized_name": normalized_name}
            if bucket_id:
                insert_data["bucket_id"] = bucket_id

            result = client.table("topic_clusters").insert(insert_data).execute()
            cluster_id = result.data[0]["id"]

        # Add topics to cluster (upsert to avoid duplicates)
        for topic in topics:
            try:
                client.table("cluster_topics").upsert({
                    "cluster_id": cluster_id,
                    "topic": topic,
                }).execute()
            except:
                pass  # Ignore duplicates

        return cluster_id

    except Exception as e:
        logger.error(f"Error saving cluster '{normalized_name}': {e}")
        return None


def save_trending_topic(
    cluster_id: str,
    channel_count: int,
    video_count: int,
    avg_performance: float,
    video_ids: list[str],
    period_start: datetime,
    period_end: datetime,
    bucket_id: str = None,
) -> bool:
    """Save a trending topic snapshot."""
    client = get_client()

    try:
        insert_data = {
            "cluster_id": cluster_id,
            "channel_count": channel_count,
            "video_count": video_count,
            "avg_performance": avg_performance,
            "video_ids": video_ids,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }
        if bucket_id:
            insert_data["bucket_id"] = bucket_id

        client.table("trending_topics").insert(insert_data).execute()
        return True
    except Exception as e:
        logger.error(f"Error saving trending topic: {e}")
        return False


def clear_old_trends() -> int:
    """
    Clear old trending topics before running new detection.
    Keeps only the latest detection run per bucket.

    Returns:
        Number of deleted records.
    """
    client = get_client()

    try:
        # Delete all existing trends (we regenerate fresh each run)
        result = client.table("trending_topics").delete().neq("id", 0).execute()
        count = len(result.data) if result.data else 0
        if count > 0:
            logger.info(f"Cleared {count} old trending topics")
        return count
    except Exception as e:
        logger.error(f"Error clearing old trends: {e}")
        return 0


def get_trending_topics(limit: int = 20) -> list[dict]:
    """
    Get the most recent trending topics.

    Returns list of trending topics with cluster info.
    """
    client = get_client()

    try:
        # Get latest trending topics (active and fading only)
        result = client.table("trending_topics").select(
            "*, topic_clusters(normalized_name)"
        ).in_("status", ["active", "fading"]).order("channel_count", desc=True).limit(limit).execute()

        return result.data
    except Exception as e:
        logger.error(f"Error getting trending topics: {e}")
        return []


def get_existing_topic_clusters(bucket_id: str) -> dict[str, str]:
    """
    Get mapping of raw topics to their cluster IDs for a bucket.

    Args:
        bucket_id: The bucket ID to get clusters for

    Returns:
        Dict mapping topic string -> cluster_id
    """
    client = get_client()

    try:
        # Get all clusters for this bucket
        clusters_result = client.table("topic_clusters").select(
            "id"
        ).eq("bucket_id", bucket_id).execute()

        if not clusters_result.data:
            return {}

        cluster_ids = [c["id"] for c in clusters_result.data]

        # Get all topics for these clusters
        topics_result = client.table("cluster_topics").select(
            "topic, cluster_id"
        ).in_("cluster_id", cluster_ids).execute()

        return {row["topic"]: row["cluster_id"] for row in topics_result.data}
    except Exception as e:
        logger.error(f"Error getting existing topic clusters: {e}")
        return {}


def get_cluster_name(cluster_id: str) -> Optional[str]:
    """Get the normalized name for a cluster."""
    client = get_client()

    try:
        result = client.table("topic_clusters").select(
            "normalized_name"
        ).eq("id", cluster_id).limit(1).execute()

        if result.data:
            return result.data[0]["normalized_name"]
        return None
    except Exception as e:
        logger.error(f"Error getting cluster name: {e}")
        return None


def upsert_trending_topic(
    cluster_id: str,
    bucket_id: str,
    channel_count: int,
    video_count: int,
    avg_performance: Optional[float],
    video_ids: list[str],
    period_start: datetime,
    period_end: datetime,
) -> bool:
    """
    Update existing trend or create new one.
    Sets status based on channel_count.

    Args:
        cluster_id: The cluster this trend belongs to
        bucket_id: The bucket this trend belongs to
        channel_count: Number of unique channels
        video_count: Number of videos
        avg_performance: Average performance ratio
        video_ids: List of video IDs
        period_start: Start of lookback period
        period_end: End of lookback period

    Returns:
        True if successful
    """
    client = get_client()

    # Determine status based on channel count
    if channel_count >= 2:
        status = "active"
    elif channel_count == 1:
        status = "fading"
    else:
        status = "inactive"

    try:
        # Try to find existing trend for this cluster+bucket
        existing = client.table("trending_topics").select(
            "id, first_detected_at"
        ).eq("cluster_id", cluster_id).eq("bucket_id", bucket_id).limit(1).execute()

        if existing.data:
            # Update existing trend
            trend_id = existing.data[0]["id"]
            client.table("trending_topics").update({
                "channel_count": channel_count,
                "video_count": video_count,
                "avg_performance": avg_performance,
                "video_ids": video_ids,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "status": status,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", trend_id).execute()
            logger.debug(f"Updated trend {trend_id} with status={status}")
        else:
            # Create new trend
            client.table("trending_topics").insert({
                "cluster_id": cluster_id,
                "bucket_id": bucket_id,
                "channel_count": channel_count,
                "video_count": video_count,
                "avg_performance": avg_performance,
                "video_ids": video_ids,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "status": status,
                "first_detected_at": datetime.now(timezone.utc).isoformat(),
            }).execute()
            logger.debug(f"Created new trend for cluster {cluster_id}")

        return True
    except Exception as e:
        logger.error(f"Error upserting trending topic: {e}")
        return False


def mark_stale_trends_inactive(bucket_id: str, active_cluster_ids: list[str]) -> int:
    """
    Mark trends as inactive if their cluster wasn't updated this run.

    Args:
        bucket_id: The bucket to update
        active_cluster_ids: List of cluster IDs that are still active

    Returns:
        Number of trends marked inactive
    """
    client = get_client()

    try:
        # Get all active/fading trends for this bucket
        result = client.table("trending_topics").select(
            "id, cluster_id"
        ).eq("bucket_id", bucket_id).in_("status", ["active", "fading"]).execute()

        if not result.data:
            return 0

        # Find trends whose clusters weren't in this run
        stale_ids = [
            row["id"] for row in result.data
            if row["cluster_id"] not in active_cluster_ids
        ]

        if not stale_ids:
            return 0

        # Mark them inactive
        client.table("trending_topics").update({
            "status": "inactive",
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }).in_("id", stale_ids).execute()

        logger.info(f"Marked {len(stale_ids)} stale trends as inactive")
        return len(stale_ids)
    except Exception as e:
        logger.error(f"Error marking stale trends inactive: {e}")
        return 0
