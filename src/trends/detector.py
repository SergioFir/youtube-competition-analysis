"""
Trend Detector.
Main orchestration for detecting trending topics across channels.
"""

from datetime import datetime, timedelta, timezone
from collections import defaultdict
from loguru import logger

from src.config import Config
from src.database.topics import (
    get_all_topics_for_trending,
    save_cluster,
    save_trending_topic,
)
from src.trends.clustering import cluster_topics


def detect_trends() -> list[dict]:
    """
    Run trend detection.

    1. Get all topics from high-performing videos in the last 14 days
    2. Cluster similar topics together
    3. Filter clusters with 3+ channels
    4. Save as trending topics

    Returns:
        List of detected trends.
    """
    logger.info("Starting trend detection...")

    # Get all topics from qualifying videos
    topic_data = get_all_topics_for_trending()

    if not topic_data:
        logger.info("No qualifying topics found for trend detection")
        return []

    logger.info(f"Found {len(topic_data)} topic entries from qualifying videos")

    # Extract just the topic strings for clustering
    all_topics = [t["topic"] for t in topic_data]

    # Cluster similar topics
    logger.info("Clustering topics...")
    clusters = cluster_topics(all_topics)

    if not clusters.get("clusters"):
        logger.info("No clusters generated")
        return []

    logger.info(f"Created {len(clusters['clusters'])} clusters")

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

        # Check if meets threshold
        if channel_count < Config.TREND_MIN_CHANNELS:
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

        # Save cluster to database
        cluster_id = save_cluster(cluster_name, cluster_topics_list)

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
            )

            trend = {
                "cluster_id": cluster_id,
                "name": cluster_name,
                "channel_count": channel_count,
                "video_count": video_count,
                "avg_performance": avg_performance,
                "video_ids": video_ids,
            }
            trends.append(trend)

            logger.info(
                f"🔥 TREND: '{cluster_name}' - "
                f"{channel_count} channels, {video_count} videos, "
                f"{avg_performance}x avg performance"
            )

    logger.info(f"Trend detection complete. Found {len(trends)} trending topics.")
    return trends


def get_trend_summary() -> dict:
    """
    Get a summary of current trends for display.

    Returns:
        Dict with trends and stats.
    """
    from src.database.topics import get_trending_topics

    trends = get_trending_topics(limit=20)

    return {
        "count": len(trends),
        "trends": trends,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
