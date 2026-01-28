"""
Backfill topics for existing videos.

This script:
1. Gets all videos with 24h snapshots that perform above 1.5x baseline
2. Extracts topics for videos that don't have them yet
3. Runs trend detection

Usage:
    python -m scripts.backfill_topics [--all] [--detect-only]

Options:
    --all           Process ALL videos, not just high performers
    --detect-only   Skip extraction, just run trend detection
"""

import sys
import argparse
from datetime import datetime, timedelta, timezone
from loguru import logger

# Add parent dir to path for imports
sys.path.insert(0, ".")

from src.config import Config
from src.database.connection import get_client
from src.database.topics import add_video_topics, video_has_topics
from src.trends.extractor import extract_topics_for_video
from src.trends.detector import detect_trends


def get_videos_to_process(all_videos: bool = False) -> list[dict]:
    """
    Get videos that need topic extraction.

    Args:
        all_videos: If True, get all videos. If False, only high performers.

    Returns:
        List of video dicts with id, title, channel_id.
    """
    client = get_client()
    cutoff = datetime.now(timezone.utc) - timedelta(days=Config.TREND_WINDOW_DAYS)

    # Get videos with 24h snapshots (note: description not stored in DB)
    videos_result = client.table("videos").select(
        "video_id, channel_id, title, published_at, is_short"
    ).gte("published_at", cutoff.isoformat()).execute()

    if not videos_result.data:
        return []

    video_ids = [v["video_id"] for v in videos_result.data]

    # Get 24h snapshots
    snapshots_result = client.table("snapshots").select(
        "video_id, views"
    ).eq("window_type", "24h").in_("video_id", video_ids).execute()

    snapshots = {s["video_id"]: s["views"] for s in snapshots_result.data}

    if all_videos:
        # Return all videos with 24h snapshots
        return [
            v for v in videos_result.data
            if v["video_id"] in snapshots
        ]

    # Get baselines for filtering
    baselines_result = client.table("channel_baselines").select(
        "channel_id, is_short, median_views"
    ).eq("window_type", "24h").execute()

    baselines = {}
    for b in baselines_result.data:
        key = (b["channel_id"], b["is_short"])
        baselines[key] = b["median_views"]

    # Filter to high performers only
    high_performers = []
    for video in videos_result.data:
        vid = video["video_id"]
        if vid not in snapshots:
            continue

        views = snapshots[vid]
        baseline = baselines.get((video["channel_id"], video["is_short"]), 0)

        if baseline > 0:
            performance = views / baseline
            if performance >= Config.TREND_MIN_PERFORMANCE:
                video["performance"] = round(performance, 2)
                high_performers.append(video)
        else:
            # No baseline = include it
            video["performance"] = None
            high_performers.append(video)

    return high_performers


def backfill_topics(videos: list[dict]) -> dict:
    """
    Extract topics for videos that don't have them.

    Returns:
        Dict with stats: processed, skipped, errors.
    """
    stats = {"processed": 0, "skipped": 0, "errors": 0}

    total = len(videos)
    logger.info(f"Processing {total} videos for topic extraction...")

    for i, video in enumerate(videos, 1):
        vid = video["video_id"]
        title = video["title"]

        # Check if already has topics
        if video_has_topics(vid):
            logger.debug(f"[{i}/{total}] Skipping {vid} - already has topics")
            stats["skipped"] += 1
            continue

        logger.info(f"[{i}/{total}] Extracting topics for: {title[:50]}...")

        try:
            # Note: description not stored in DB, will rely on transcript + title
            topics = extract_topics_for_video(
                video_id=vid,
                title=title,
                description="",  # Will fallback to transcript
            )

            if topics:
                add_video_topics(vid, topics)
                logger.info(f"  → Topics: {', '.join(topics)}")
                stats["processed"] += 1
            else:
                logger.warning(f"  → No topics extracted")
                stats["errors"] += 1

        except Exception as e:
            logger.error(f"  → Error: {e}")
            stats["errors"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Backfill topics for existing videos")
    parser.add_argument("--all", action="store_true", help="Process all videos, not just high performers")
    parser.add_argument("--detect-only", action="store_true", help="Skip extraction, just run trend detection")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("TOPIC BACKFILL SCRIPT")
    logger.info("=" * 60)

    if not args.detect_only:
        # Validate OpenRouter config
        if not Config.OPENROUTER_API_KEY:
            logger.error("OPENROUTER_API_KEY is not set. Please add it to your .env file.")
            sys.exit(1)

        logger.info(f"Using model: {Config.OPENROUTER_MODEL}")
        logger.info(f"Trend window: {Config.TREND_WINDOW_DAYS} days")
        logger.info(f"Min performance: {Config.TREND_MIN_PERFORMANCE}x baseline")
        logger.info(f"Min channels for trend: {Config.TREND_MIN_CHANNELS}")

        # Get videos to process
        videos = get_videos_to_process(all_videos=args.all)
        logger.info(f"Found {len(videos)} videos to process")

        if videos:
            # Extract topics
            stats = backfill_topics(videos)
            logger.info("")
            logger.info("Extraction complete:")
            logger.info(f"  Processed: {stats['processed']}")
            logger.info(f"  Skipped (already had topics): {stats['skipped']}")
            logger.info(f"  Errors: {stats['errors']}")

    # Run trend detection
    logger.info("")
    logger.info("=" * 60)
    logger.info("RUNNING TREND DETECTION")
    logger.info("=" * 60)

    trends = detect_trends()

    if trends:
        logger.info("")
        logger.info("🔥 TRENDING TOPICS:")
        for trend in trends:
            logger.info(
                f"  • {trend['name']} - "
                f"{trend['channel_count']} channels, "
                f"{trend['video_count']} videos, "
                f"{trend['avg_performance']}x avg"
            )
    else:
        logger.info("No trends detected (need 3+ channels per topic)")

    logger.info("")
    logger.info("Done!")


if __name__ == "__main__":
    main()
