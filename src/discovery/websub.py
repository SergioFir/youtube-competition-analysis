"""
WebSub (PubSubHubbub) discovery.
Receives push notifications from YouTube when new videos are published.
Used in production for real-time video discovery.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import xml.etree.ElementTree as ET
import httpx
from loguru import logger

from src.config import Config
from src.database.connection import get_client
from src.database.videos import video_exists, add_video
from src.database.snapshots import add_snapshot
from src.youtube.api import YouTubeAPI, YouTubeAPIError
from src.youtube.shorts_detector import detect_short_with_fallback


class WebSubSubscription:
    """
    Manages WebSub subscriptions for YouTube channel feeds.

    YouTube uses Google's PubSubHubbub hub at https://pubsubhubbub.appspot.com/subscribe
    to push notifications when new videos are published.
    """

    FEED_URL_TEMPLATE = "https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"

    def __init__(self):
        self.hub_url = Config.WEBSUB_HUB_URL
        self.callback_url = Config.WEBSUB_CALLBACK_URL
        self.lease_seconds = Config.WEBSUB_LEASE_SECONDS
        self.youtube_api = YouTubeAPI()

    def get_feed_url(self, channel_id: str) -> str:
        """Get the YouTube feed URL for a channel."""
        return self.FEED_URL_TEMPLATE.format(channel_id=channel_id)

    def subscribe(self, channel_id: str) -> bool:
        """
        Subscribe to a channel's feed via WebSub.

        Returns:
            True if subscription request was accepted (202), False otherwise.
        """
        if not self.callback_url:
            logger.error("WEBSUB_CALLBACK_URL not configured")
            return False

        feed_url = self.get_feed_url(channel_id)

        data = {
            "hub.callback": self.callback_url,
            "hub.topic": feed_url,
            "hub.verify": "async",
            "hub.mode": "subscribe",
            "hub.lease_seconds": str(self.lease_seconds),
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.hub_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )

            if response.status_code == 202:
                logger.info(f"WebSub subscription requested for channel {channel_id}")
                # Store subscription info
                self._save_subscription(channel_id, feed_url)
                return True
            else:
                logger.error(
                    f"WebSub subscription failed for {channel_id}: "
                    f"{response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error subscribing to {channel_id}: {e}")
            return False

    def unsubscribe(self, channel_id: str) -> bool:
        """
        Unsubscribe from a channel's feed.

        Returns:
            True if unsubscription request was accepted, False otherwise.
        """
        if not self.callback_url:
            return False

        feed_url = self.get_feed_url(channel_id)

        data = {
            "hub.callback": self.callback_url,
            "hub.topic": feed_url,
            "hub.verify": "async",
            "hub.mode": "unsubscribe",
        }

        try:
            with httpx.Client() as client:
                response = client.post(
                    self.hub_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )

            if response.status_code == 202:
                logger.info(f"WebSub unsubscription requested for channel {channel_id}")
                self._remove_subscription(channel_id)
                return True
            else:
                logger.warning(f"WebSub unsubscription failed for {channel_id}: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error unsubscribing from {channel_id}: {e}")
            return False

    def _save_subscription(self, channel_id: str, feed_url: str):
        """Save subscription info to database."""
        client = get_client()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.lease_seconds)

        try:
            client.table("websub_subscriptions").upsert({
                "channel_id": channel_id,
                "feed_url": feed_url,
                "callback_url": self.callback_url,
                "subscribed_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires_at.isoformat(),
                "is_active": True,
            }).execute()
        except Exception as e:
            logger.error(f"Error saving subscription for {channel_id}: {e}")

    def _remove_subscription(self, channel_id: str):
        """Remove subscription from database."""
        client = get_client()
        try:
            client.table("websub_subscriptions").update({
                "is_active": False,
            }).eq("channel_id", channel_id).execute()
        except Exception as e:
            logger.error(f"Error removing subscription for {channel_id}: {e}")


class WebSubHandler:
    """
    Handles incoming WebSub notifications and verification requests.
    """

    def __init__(self):
        self.youtube_api = YouTubeAPI()

    def verify_subscription(
        self,
        mode: str,
        topic: str,
        challenge: str,
        lease_seconds: Optional[str] = None,
    ) -> Optional[str]:
        """
        Handle WebSub verification request (GET).

        YouTube hub sends this to verify we want the subscription.
        We must respond with the challenge to confirm.

        Args:
            mode: "subscribe" or "unsubscribe"
            topic: The feed URL being subscribed to
            challenge: Random string we must echo back
            lease_seconds: How long the subscription will last

        Returns:
            The challenge string if verification succeeds, None otherwise.
        """
        logger.info(f"WebSub verification: mode={mode}, topic={topic}")

        # Extract channel_id from topic URL
        if "channel_id=" in topic:
            channel_id = topic.split("channel_id=")[1].split("&")[0]
            logger.info(f"Verification for channel: {channel_id}")
        else:
            logger.warning(f"Could not extract channel_id from topic: {topic}")

        # Always accept subscription verifications
        # In a more secure setup, you'd verify the channel_id is one we expect
        if mode in ("subscribe", "unsubscribe"):
            logger.info(f"Accepting {mode} verification")
            return challenge

        logger.warning(f"Unknown verification mode: {mode}")
        return None

    def handle_notification(self, body: bytes, received_at: Optional[datetime] = None) -> dict:
        """
        Handle incoming WebSub notification (POST).

        YouTube sends an Atom feed with the new/updated video.

        Args:
            body: Raw XML body of the notification
            received_at: Timestamp when webhook received the notification

        Returns:
            Summary dict with videos processed.
        """
        if received_at is None:
            received_at = datetime.now(timezone.utc)

        summary = {
            "videos_processed": 0,
            "videos_skipped": 0,
            "errors": 0,
        }

        try:
            # Parse XML
            root = ET.fromstring(body)

            # Define namespaces
            ns = {
                "atom": "http://www.w3.org/2005/Atom",
                "yt": "http://www.youtube.com/xml/schemas/2015",
            }

            # Find all entry elements (videos)
            entries = root.findall("atom:entry", ns)

            if not entries:
                # Try without namespace (sometimes YouTube sends it differently)
                entries = root.findall("entry")

            logger.info(f"WebSub notification contains {len(entries)} entries")

            for entry in entries:
                try:
                    # Extract video ID
                    video_id_elem = entry.find("yt:videoId", ns)
                    if video_id_elem is None:
                        video_id_elem = entry.find("{http://www.youtube.com/xml/schemas/2015}videoId")

                    if video_id_elem is None:
                        logger.warning("Entry missing video ID")
                        summary["errors"] += 1
                        continue

                    video_id = video_id_elem.text

                    # Extract channel ID
                    channel_id_elem = entry.find("yt:channelId", ns)
                    if channel_id_elem is None:
                        channel_id_elem = entry.find("{http://www.youtube.com/xml/schemas/2015}channelId")

                    if channel_id_elem is None:
                        logger.warning(f"Entry missing channel ID for video {video_id}")
                        summary["errors"] += 1
                        continue

                    channel_id = channel_id_elem.text

                    # Extract published time from feed
                    published_elem = entry.find("atom:published", ns)
                    if published_elem is None:
                        published_elem = entry.find("published")

                    if published_elem is not None and published_elem.text:
                        try:
                            published_at = datetime.fromisoformat(published_elem.text.replace("Z", "+00:00"))
                            delay_seconds = (received_at - published_at).total_seconds()
                            delay_minutes = delay_seconds / 60

                            logger.info(
                                f"⏱️  WebSub Latency - Video {video_id}: "
                                f"Published: {published_at.isoformat()}, "
                                f"Received: {received_at.isoformat()}, "
                                f"Delay: {delay_seconds:.1f}s ({delay_minutes:.2f} min)"
                            )
                        except Exception as e:
                            logger.warning(f"Could not parse published time: {e}")

                    # Check if video already exists
                    if video_exists(video_id):
                        logger.debug(f"Video {video_id} already exists, skipping")
                        summary["videos_skipped"] += 1
                        continue

                    # Process new video
                    result = self._process_new_video(video_id, channel_id)
                    if result:
                        summary["videos_processed"] += 1
                    else:
                        summary["errors"] += 1

                except Exception as e:
                    logger.error(f"Error processing entry: {e}")
                    summary["errors"] += 1

        except ET.ParseError as e:
            logger.error(f"Error parsing WebSub notification XML: {e}")
            summary["errors"] += 1

        return summary

    def _process_new_video(self, video_id: str, channel_id: str) -> Optional[dict]:
        """
        Process a newly discovered video from WebSub notification.
        Same logic as polling discovery.

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

            logger.info(f"WebSub: Discovered new video {video_id} ({details['title'][:50]}...)")
            return video

        except YouTubeAPIError as e:
            logger.error(f"YouTube API error for {video_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error processing video {video_id}: {e}")
            return None


def subscribe_all_channels() -> dict:
    """
    Subscribe to WebSub notifications for all active channels.

    Returns:
        Summary dict with success/failure counts.
    """
    from src.database.channels import get_active_channels

    subscription = WebSubSubscription()
    channels = get_active_channels()

    summary = {
        "total": len(channels),
        "subscribed": 0,
        "failed": 0,
    }

    for channel in channels:
        channel_id = channel["channel_id"]
        if subscription.subscribe(channel_id):
            summary["subscribed"] += 1
        else:
            summary["failed"] += 1

    logger.info(f"WebSub subscription summary: {summary}")
    return summary


def renew_expiring_subscriptions() -> dict:
    """
    Renew WebSub subscriptions that are about to expire.
    Should be run periodically (e.g., daily).

    Returns:
        Summary dict with renewals.
    """
    client = get_client()
    subscription = WebSubSubscription()

    # Find subscriptions expiring within the buffer period
    buffer_hours = Config.WEBSUB_RENEWAL_BUFFER_HOURS
    threshold = datetime.now(timezone.utc) + timedelta(hours=buffer_hours)

    try:
        result = client.table("websub_subscriptions").select(
            "channel_id"
        ).eq(
            "is_active", True
        ).lt(
            "expires_at", threshold.isoformat()
        ).execute()

        expiring = result.data
    except Exception as e:
        logger.error(f"Error fetching expiring subscriptions: {e}")
        return {"error": str(e)}

    summary = {
        "expiring": len(expiring),
        "renewed": 0,
        "failed": 0,
    }

    for sub in expiring:
        channel_id = sub["channel_id"]
        logger.info(f"Renewing subscription for {channel_id}")
        if subscription.subscribe(channel_id):  # Subscribe again to renew
            summary["renewed"] += 1
        else:
            summary["failed"] += 1

    logger.info(f"WebSub renewal summary: {summary}")
    return summary
