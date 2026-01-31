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
    get_existing_topic_clusters,
    get_cluster_name,
    upsert_trending_topic,
    mark_stale_trends_inactive,
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
    Uses persistent clustering - only new topics are sent to AI.

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
        # Mark all existing trends as inactive since no qualifying videos
        mark_stale_trends_inactive(bucket_id, [])
        return []

    logger.info(f"Found {len(topic_data)} topic entries for '{bucket_name}'")

    # Build lookup: topic -> video data
    topic_to_videos = defaultdict(list)
    for entry in topic_data:
        topic_to_videos[entry["topic"]].append(entry)

    # Get existing topic -> cluster mapping
    existing_topic_to_cluster = get_existing_topic_clusters(bucket_id)
    logger.info(f"Found {len(existing_topic_to_cluster)} existing topic mappings")

    # Separate topics into known (already clustered) and new
    all_topics = list(topic_to_videos.keys())
    known_topics = [t for t in all_topics if t in existing_topic_to_cluster]
    new_topics = [t for t in all_topics if t not in existing_topic_to_cluster]

    logger.info(f"Topics: {len(known_topics)} known, {len(new_topics)} new")

    # Build cluster -> topics mapping from known topics
    cluster_to_topics = defaultdict(list)
    for topic in known_topics:
        cluster_id = existing_topic_to_cluster[topic]
        cluster_to_topics[cluster_id].append(topic)

    # Only cluster NEW topics with AI
    if new_topics:
        logger.info(f"Clustering {len(new_topics)} new topics for '{bucket_name}'...")
        new_clusters = cluster_topics(new_topics, context=f"These are topics from {bucket_name} YouTube channels")

        if new_clusters.get("clusters"):
            logger.info(f"AI created {len(new_clusters['clusters'])} clusters from new topics")

            # Save new clusters and add to mapping
            for cluster in new_clusters["clusters"]:
                cluster_name = cluster["name"]
                cluster_topics_list = cluster["topics"]

                # Save cluster to database
                cluster_id = save_cluster(cluster_name, cluster_topics_list, bucket_id=bucket_id)
                if cluster_id:
                    for topic in cluster_topics_list:
                        cluster_to_topics[cluster_id].append(topic)
    else:
        logger.info(f"No new topics to cluster for '{bucket_name}'")

    # Now calculate stats for ALL clusters (both existing and new)
    trends = []
    active_cluster_ids = []
    period_end = datetime.now(timezone.utc)
    period_start = period_end - timedelta(days=Config.TREND_WINDOW_DAYS)

    for cluster_id, topics_in_cluster in cluster_to_topics.items():
        # Gather all videos in this cluster
        videos_in_cluster = []
        seen_video_ids = set()

        for topic in topics_in_cluster:
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

        # Calculate stats
        video_count = len(videos_in_cluster)
        performances = [
            v["performance_ratio"]
            for v in videos_in_cluster
            if v.get("performance_ratio") is not None
        ]
        avg_performance = round(sum(performances) / len(performances), 2) if performances else None
        video_ids = list(seen_video_ids)

        # Upsert the trending topic (update if exists, create if new)
        upsert_trending_topic(
            cluster_id=cluster_id,
            bucket_id=bucket_id,
            channel_count=channel_count,
            video_count=video_count,
            avg_performance=avg_performance,
            video_ids=video_ids,
            period_start=period_start,
            period_end=period_end,
        )

        active_cluster_ids.append(cluster_id)

        # Get cluster name for logging
        cluster_name = get_cluster_name(cluster_id) or "unknown"

        # Only report as trend if meets threshold
        min_channels = max(2, min(Config.TREND_MIN_CHANNELS, len(channel_ids) // 2))
        if channel_count >= min_channels:
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

    # Mark clusters not seen this run as inactive
    mark_stale_trends_inactive(bucket_id, active_cluster_ids)

    return trends


def detect_trends() -> list[dict]:
    """
    Run trend detection for all buckets.
    Uses persistent clustering - trends are updated, not deleted.

    Returns:
        List of all detected trends across buckets.
    """
    logger.info("Starting per-bucket trend detection (with persistence)...")

    # No longer clear old trends - we update them instead

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
