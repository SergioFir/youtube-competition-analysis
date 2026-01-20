"""
RSS Polling discovery.
Checks channel RSS feeds for new videos.
Used for local development (production will use WebSub).
"""

from datetime import datetime
from typing import Optional
import feedparser
from loguru import logger

from src.database.channels import get_active_channels
from src.database.videos import video_exists, add_video
from src.database.snapshots import add_snapshot
from src.youtube.api import YouTubeAPI, YouTubeAPIError
from src.youtube.shorts_detector import detect_short_with_fallback


class PollingDiscovery:
    """
    Discovers new videos by polling YouTube RSS feeds.
    """

    RSS_URL_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    def __init__(self):
        self.youtube_api = YouTubeAPI()

    def get_feed_url(self, channel_id: str) -> str:
        """Get RSS feed URL for a channel."""
        return self.RSS_URL_TEMPLATE.format(channel_id=channel_id)

    def fetch_recent_videos(self, channel_id: str) -> list[dict]:
        """
        Fetch recent videos from a channel's RSS feed.

        Returns:
            List of dicts with video_id, title, published_at
        """
        url = self.get_feed_url(channel_id)

        try:
            feed = feedparser.parse(url)

            if feed.bozo:  # Feed parsing error
                logger.warning(f"Error parsing feed for {channel_id}: {feed.bozo_exception}")
                return []

            videos = []
            for entry in feed.entries:
                # Extract video ID from the link
                video_id = entry.get("yt_videoid")
                if not video_id:
                    # Try to extract from link
                    link = entry.get("link", "")
                    if "v=" in link:
                        video_id = link.split("v=")[1].split("&")[0]

                if video_id:
                    videos.append({
                        "video_id": video_id,
                        "title": entry.get("title", ""),
                        "published_at": entry.get("published", ""),
                    })

            return videos

        except Exception as e:
            logger.error(f"Error fetching feed for {channel_id}: {e}")
            return []

    def discover_new_video(self, video_id: str, channel_id: str) -> Optional[dict]:
        """
        Process a newly discovered video:
        1. Get full details from YouTube API
        2. Check if it's a Short
        3. Add to database
        4. Take T+0 snapshot

        Returns:
            The created video record, or None if failed.
        """
        try:
            # Get video details from API
            details = self.youtube_api.get_video_details(video_id)
            if not details:
                logger.warning(f"Could not get details for video {video_id}")
                return None

            # Check if it's a Short
            is_short = detect_short_with_fallback(video_id, details["duration_seconds"])

            # Parse published_at
            published_at = datetime.fromisoformat(details["published_at"].replace("Z", "+00:00"))

            # Add video to database
            video = add_video(
                video_id=video_id,
                channel_id=channel_id,
                published_at=published_at,
                title=details["title"],
                duration_seconds=details["duration_seconds"],
                is_short=is_short,
            )

            if not video:
                logger.error(f"Failed to add video {video_id} to database")
                return None

            # Take T+0 snapshot immediately
            add_snapshot(
                video_id=video_id,
                window_type="0h",
                views=details["views"],
                likes=details["likes"],
                comments=details["comments"],
            )

            logger.info(f"Discovered new video: {video_id} ({details['title'][:50]}...)")
            return video

        except YouTubeAPIError as e:
            logger.error(f"YouTube API error for {video_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")
            return None

    def poll_all_channels(self) -> dict:
        """
        Poll all active channels for new videos.

        Returns:
            Summary dict with channels_checked, new_videos_found, errors.
        """
        channels = get_active_channels()
        summary = {
            "channels_checked": 0,
            "new_videos_found": 0,
            "errors": 0,
        }

        for channel in channels:
            channel_id = channel["channel_id"]
            summary["channels_checked"] += 1

            try:
                recent_videos = self.fetch_recent_videos(channel_id)

                for video_data in recent_videos:
                    video_id = video_data["video_id"]

                    # Skip if already in database
                    if video_exists(video_id):
                        continue

                    # Process new video
                    result = self.discover_new_video(video_id, channel_id)
                    if result:
                        summary["new_videos_found"] += 1

            except Exception as e:
                logger.error(f"Error polling channel {channel_id}: {e}")
                summary["errors"] += 1

        return summary

    def poll_single_channel(self, channel_id: str) -> dict:
        """
        Poll a single channel for new videos.

        Returns:
            Summary dict with new_videos_found, errors.
        """
        summary = {
            "channel_id": channel_id,
            "new_videos_found": 0,
            "videos": [],
        }

        try:
            recent_videos = self.fetch_recent_videos(channel_id)

            for video_data in recent_videos:
                video_id = video_data["video_id"]

                if video_exists(video_id):
                    continue

                result = self.discover_new_video(video_id, channel_id)
                if result:
                    summary["new_videos_found"] += 1
                    summary["videos"].append(result)

        except Exception as e:
            logger.error(f"Error polling channel {channel_id}: {e}")
            summary["error"] = str(e)

        return summary
