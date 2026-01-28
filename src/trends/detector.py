"""
Trend Detector.
Main orchestration for detecting trending topics per bucket.
"""

from datetime import datetime, timedelta, timezone
from collections import defaultdict
from loguru import logger

from src.config import Config
from src.database.topics import (
    get_topics_for_bucket,
    save_cluster,
    save_trending_topic,
    clear_old_trends,
)
from src.trends.clustering import cluster_topics


def get_all_buckets() -> list[dict]:
    """Get all buckets with their channels."""
    from src.database.connection import get_client
    client = get_client()

    try:
        # Get buckets
        buckets_result = client.table("buckets").select("*").execute()
        buckets = buckets_result.data or []

        # Get bucket-channel mappings
        bc_result = client.table("bucket_channels").select("*").execute()
        bucket_channels = bc_result.data or []

        # Build bucket -> channel_ids mapping
        for bucket in buckets:
            bucket["channel_ids"] = [
                bc["channel_id"]
                for bc in bucket_channels
                if bc["bucket_id"] == bucket["id"]
            ]

        return buckets
    except Exception as e:
        logger.error(f"Error fetching buckets: {e}")
        return []


def detect_trends_for_bucket(bucket: dict) -> list[dict]:
    """
    Run trend detection for a single bucket.

    Args:
        bucket: Bucket dict with id, name, and channel_ids

    Returns:
        List of detected trends for this bucket.
    """
    bucket_id = bucket["id"]
    bucket_name = bucket["name"]
    channel_ids = bucket.get("channel_ids", [])

    if not channel_ids:
        logger.debug(f"Bucket '{bucket_name}' has no channels, skipping")
        return []

    logger.info(f"Detecting trends for bucket '{bucket_name}' ({len(channel_ids)} channels)...")

    # Get topics from videos in this bucket's channels
    topic_data = get_topics_for_bucket(channel_ids)

    if not topic_data:
        logger.info(f"No qualifying topics for bucket '{bucket_name}'")
        return []

    logger.info(f"Found {len(topic_data)} topic entries for '{bucket_name}'")

    # Extract just the topic strings for clustering
    all_topics = [t["topic"] for t in topic_data]

    # Cluster similar topics (with bucket context in prompt)
    logger.info(f"Clustering topics for '{bucket_name}'...")
    clusters = cluster_topics(all_topics, context=f"These are topics from {bucket_name} YouTube channels")

    if not clusters.get("clusters"):
        logger.info(f"No clusters generated for '{bucket_name}'")
        return []

    logger.info(f"Created {len(clusters['clusters'])} clusters for '{bucket_name}'")

    # Build lookup: topic -> video data
    topic_to_videos = defaultdict(list)
    for entry in topic_data:
        topic_to_videos[entry["topic"]].append(entry)

    # Analyze each cluster
    trends = []
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=Config.TREND_WINDOW_DAYS)

    for cluster in clusters["clusters"]:
        cluster_name = cluster["name"]
        cluster_topics_list = cluster["topics"]

        # Gather all videos in this cluster
        videos_in_cluster = []
        seen_video_ids = set()

        for topic in cluster_topics_list:
            for video_entry in topic_to_videos.get(topic, []):
                vid = video_entry["video_id"]
                if vid not in seen_video_ids:
                    seen_video_ids.add(vid)
                    videos_in_cluster.append(video_entry)

        if not videos_in_cluster:
            continue

        # Count unique channels
        unique_channels = set(v["channel_id"] for v in videos_in_cluster)
        channel_count = len(unique_channels)

        # Check if meets threshold (2+ channels for bucket-level trends)
        min_channels = max(2, min(Config.TREND_MIN_CHANNELS, len(channel_ids) // 2))
        if channel_count < min_channels:
            continue

        # Calculate stats
        video_count = len(videos_in_cluster)
        performances = [
            v["performance_ratio"]
            for v in videos_in_cluster
            if v.get("performance_ratio") is not None
        ]
        avg_performance = round(sum(performances) / len(performances), 2) if performances else None
        video_ids = list(seen_video_ids)

        # Save cluster to database (with bucket_id)
        cluster_id = save_cluster(cluster_name, cluster_topics_list, bucket_id=bucket_id)

        if cluster_id:
            # Save as trending topic
            save_trending_topic(
                cluster_id=cluster_id,
                channel_count=channel_count,
                video_count=video_count,
                avg_performance=avg_performance,
                video_ids=video_ids,
                period_start=period_start,
                period_end=period_end,
                bucket_id=bucket_id,
            )

            trend = {
                "bucket_id": bucket_id,
                "bucket_name": bucket_name,
                "cluster_id": cluster_id,
                "name": cluster_name,
                "channel_count": channel_count,
                "video_count": video_count,
                "avg_performance": avg_performance,
                "video_ids": video_ids,
            }
            trends.append(trend)

            logger.info(
                f"🔥 TREND [{bucket_name}]: '{cluster_name}' - "
                f"{channel_count} channels, {video_count} videos, "
                f"{avg_performance}x avg performance"
            )

    return trends


def detect_trends() -> list[dict]:
    """
    Run trend detection for all buckets.

    Returns:
        List of all detected trends across buckets.
    """
    logger.info("Starting per-bucket trend detection...")

    # Clear old trends first
    clear_old_trends()

    # Get all buckets
    buckets = get_all_buckets()

    if not buckets:
        logger.info("No buckets found, skipping trend detection")
        return []

    logger.info(f"Found {len(buckets)} buckets")

    # Detect trends for each bucket
    all_trends = []
    for bucket in buckets:
        bucket_trends = detect_trends_for_bucket(bucket)
        all_trends.extend(bucket_trends)

    logger.info(f"Trend detection complete. Found {len(all_trends)} total trends across {len(buckets)} buckets.")
    return all_trends


def get_trend_summary() -> dict:
    """
    Get a summary of current trends for display.

    Returns:
        Dict with trends and stats.
    """
    from src.database.topics import get_trending_topics

    trends = get_trending_topics(limit=50)

    return {
        "count": len(trends),
        "trends": trends,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
