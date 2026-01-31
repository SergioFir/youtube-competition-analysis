"""
Channel Discovery System.
Discovers new competitor channels based on trending topics in a bucket.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from loguru import logger

from src.youtube.api import YouTubeAPI, YouTubeAPIError
from src.database.discovery import (
    get_discovery_settings,
    get_tracked_channel_ids,
    get_suggested_channel_ids,
    save_channel_suggestions,
    clear_pending_suggestions,
)
from src.database.connection import get_client


def get_bucket_trending_keywords(bucket_id: str, limit: int = 5) -> list[str]:
    """
    Get trending topic cluster names for a bucket.
    These serve as keywords for channel discovery.

    Args:
        bucket_id: Bucket ID
        limit: Maximum number of keywords to return

    Returns:
        List of keyword strings (cluster names)
    """
    client = get_client()

    try:
        # Get trending topics for this bucket, ordered by channel count
        result = client.table("trending_topics").select(
            "cluster_id, topic_clusters(normalized_name)"
        ).eq(
            "bucket_id", bucket_id
        ).order(
            "channel_count", desc=True
        ).limit(limit).execute()

        logger.info(f"Trending topics query for bucket {bucket_id}: {len(result.data)} results")
        logger.debug(f"Raw result: {result.data}")

        keywords = []
        for row in result.data:
            cluster = row.get("topic_clusters")
            if cluster and cluster.get("normalized_name"):
                keywords.append(cluster["normalized_name"])

        logger.info(f"Extracted keywords: {keywords}")
        return keywords

    except Exception as e:
        logger.error(f"Error getting trending keywords: {e}")
        return []


def filter_channel(
    channel: dict,
    settings: dict,
    tracked_ids: set[str],
    suggested_ids: set[str],
    youtube_api: Optional[YouTubeAPI] = None,
) -> tuple[bool, Optional[str]]:
    """
    Apply all filters to a channel.

    Args:
        channel: Channel details dict
        settings: Discovery settings dict
        tracked_ids: Set of already tracked channel IDs
        suggested_ids: Set of already suggested channel IDs
        youtube_api: YouTubeAPI instance (needed for activity check)

    Returns:
        Tuple of (passes_filter, rejection_reason)
    """
    channel_id = channel["channel_id"]

    # Hard filter: Already tracked
    if channel_id in tracked_ids:
        return False, "already_tracked"

    # Hard filter: Already suggested
    if channel_id in suggested_ids:
        return False, "already_suggested"

    # Hard filter: Hidden subscriber count
    if channel.get("hidden_subscriber_count", False):
        return False, "hidden_subscribers"

    # Configurable: Subscriber count range
    subs = channel.get("subscriber_count", 0)
    if subs < settings["min_subscribers"]:
        return False, f"subscribers_too_low ({subs} < {settings['min_subscribers']})"
    if subs > settings["max_subscribers"]:
        return False, f"subscribers_too_high ({subs} > {settings['max_subscribers']})"

    # Configurable: Video count
    videos = channel.get("video_count", 0)
    if videos < settings["min_videos"]:
        return False, f"videos_too_low ({videos} < {settings['min_videos']})"

    # Configurable: Channel age
    published_at = channel.get("published_at")
    if published_at and settings["min_channel_age_days"] > 0:
        try:
            created = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created).days
            if age_days < settings["min_channel_age_days"]:
                return False, f"channel_too_new ({age_days} < {settings['min_channel_age_days']} days)"
        except Exception:
            pass

    # Configurable: Exclude kids content
    if settings["exclude_kids_content"] and channel.get("made_for_kids", False):
        return False, "made_for_kids"

    # Configurable: Country filter
    country_filter = settings.get("country_filter")
    if country_filter and len(country_filter) > 0:
        channel_country = channel.get("country")
        if channel_country and channel_country not in country_filter:
            return False, f"country_mismatch ({channel_country})"

    # Optional: Activity check
    if settings["activity_check"] and youtube_api:
        try:
            latest_upload = youtube_api.get_channel_latest_upload(channel_id)
            if latest_upload:
                upload_date = datetime.fromisoformat(latest_upload.replace("Z", "+00:00"))
                days_since = (datetime.now(timezone.utc) - upload_date).days
                if days_since > settings["max_days_since_upload"]:
                    return False, f"inactive ({days_since} > {settings['max_days_since_upload']} days)"
        except Exception as e:
            logger.debug(f"Activity check failed for {channel_id}: {e}")

    return True, None


def discover_channels(
    bucket_id: str,
    keywords: Optional[list[str]] = None,
    max_results_per_keyword: int = 25,
    clear_pending: bool = True,
) -> dict:
    """
    Discover new channels for a bucket based on keywords.

    Args:
        bucket_id: Bucket to discover channels for
        keywords: Keywords to search (if None, uses trending topics)
        max_results_per_keyword: Max search results per keyword
        clear_pending: Whether to clear existing pending suggestions first

    Returns:
        dict with:
            - keywords_used: List of keywords searched
            - channels_found: Total channels found from search
            - channels_filtered: Channels after filtering
            - suggestions_saved: New suggestions saved
            - filter_stats: Breakdown of why channels were filtered
    """
    logger.info(f"Starting channel discovery for bucket {bucket_id}")

    # Initialize
    youtube_api = YouTubeAPI()
    settings = get_discovery_settings(bucket_id)
    tracked_ids = get_tracked_channel_ids()
    suggested_ids = get_suggested_channel_ids(bucket_id)

    # Get keywords
    if keywords is None:
        keywords = get_bucket_trending_keywords(bucket_id)

    if not keywords:
        logger.warning(f"No keywords available for bucket {bucket_id}")
        return {
            "keywords_used": [],
            "channels_found": 0,
            "channels_filtered": 0,
            "suggestions_saved": 0,
            "filter_stats": {},
            "error": "No keywords available. Run trend detection first or provide custom keywords.",
        }

    logger.info(f"Using keywords: {keywords}")

    # Clear pending suggestions if requested
    if clear_pending:
        clear_pending_suggestions(bucket_id)

    # Search for channels
    all_channel_ids = set()
    channel_keywords = {}  # channel_id -> [keywords that matched]

    for keyword in keywords:
        try:
            results = youtube_api.search_channels(keyword, max_results=max_results_per_keyword)
            logger.info(f"Keyword '{keyword}' returned {len(results)} channels")

            for result in results:
                cid = result["channel_id"]
                all_channel_ids.add(cid)
                if cid not in channel_keywords:
                    channel_keywords[cid] = []
                channel_keywords[cid].append(keyword)

        except YouTubeAPIError as e:
            logger.error(f"Search failed for keyword '{keyword}': {e}")

    logger.info(f"Found {len(all_channel_ids)} unique channels from {len(keywords)} keywords")

    if not all_channel_ids:
        return {
            "keywords_used": keywords,
            "channels_found": 0,
            "channels_filtered": 0,
            "suggestions_saved": 0,
            "filter_stats": {},
        }

    # Get full details for all channels
    try:
        channel_details = youtube_api.get_channels_full_details(list(all_channel_ids))
        logger.info(f"Retrieved details for {len(channel_details)} channels")
    except YouTubeAPIError as e:
        logger.error(f"Failed to get channel details: {e}")
        return {
            "keywords_used": keywords,
            "channels_found": len(all_channel_ids),
            "channels_filtered": 0,
            "suggestions_saved": 0,
            "filter_stats": {},
            "error": str(e),
        }

    # Apply filters
    passed_channels = []
    filter_stats = {}

    for channel in channel_details:
        passes, reason = filter_channel(
            channel,
            settings,
            tracked_ids,
            suggested_ids,
            youtube_api if settings["activity_check"] else None,
        )

        if passes:
            channel["matched_keywords"] = channel_keywords.get(channel["channel_id"], [])
            passed_channels.append(channel)
        else:
            filter_stats[reason] = filter_stats.get(reason, 0) + 1

    logger.info(f"{len(passed_channels)} channels passed filters")
    if filter_stats:
        logger.info(f"Filter stats: {filter_stats}")

    # Save suggestions
    saved = save_channel_suggestions(bucket_id, passed_channels)

    return {
        "keywords_used": keywords,
        "channels_found": len(all_channel_ids),
        "channels_filtered": len(passed_channels),
        "suggestions_saved": saved,
        "filter_stats": filter_stats,
    }
