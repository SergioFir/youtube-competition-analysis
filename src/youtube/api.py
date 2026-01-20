"""
YouTube Data API wrapper.
Handles all interactions with the YouTube API.
"""

import re
import httpx
from typing import Optional
from urllib.parse import urlparse
from src.config import Config


def parse_channel_url(url: str) -> dict:
    """
    Parse a YouTube channel URL and extract the identifier.

    Supports formats:
    - youtube.com/@handle
    - youtube.com/channel/UCxxx
    - youtube.com/c/CustomName
    - youtube.com/user/username
    - Just a handle like @JulianGoldieSEO
    - Just a channel ID like UCxxx

    Returns:
        dict with 'type' ('channel_id', 'handle', 'custom', 'user') and 'value'
    """
    url = url.strip()

    # If it's just a handle without URL
    if url.startswith('@'):
        return {'type': 'handle', 'value': url[1:]}  # Remove @

    # If it's just a channel ID (starts with UC)
    if url.startswith('UC') and len(url) == 24:
        return {'type': 'channel_id', 'value': url}

    # Parse as URL
    if not url.startswith('http'):
        url = 'https://' + url

    parsed = urlparse(url)
    path = parsed.path.strip('/')

    # youtube.com/@handle
    if path.startswith('@'):
        return {'type': 'handle', 'value': path[1:]}

    # youtube.com/channel/UCxxx
    if path.startswith('channel/'):
        channel_id = path.replace('channel/', '')
        return {'type': 'channel_id', 'value': channel_id}

    # youtube.com/c/CustomName
    if path.startswith('c/'):
        custom_name = path.replace('c/', '')
        return {'type': 'custom', 'value': custom_name}

    # youtube.com/user/username
    if path.startswith('user/'):
        username = path.replace('user/', '')
        return {'type': 'user', 'value': username}

    # Could be just youtube.com/SomeName (legacy custom URL)
    if '/' not in path and path:
        return {'type': 'custom', 'value': path}

    raise ValueError(f"Could not parse YouTube channel URL: {url}")


class YouTubeAPI:
    """Wrapper for YouTube Data API v3."""

    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or Config.YOUTUBE_API_KEY
        if not self.api_key:
            raise ValueError("YouTube API key is required")

    def _make_request(self, endpoint: str, params: dict) -> dict:
        """Make a GET request to the YouTube API."""
        params["key"] = self.api_key
        url = f"{self.BASE_URL}/{endpoint}"

        with httpx.Client() as client:
            response = client.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()

    def get_video_stats(self, video_id: str) -> Optional[dict]:
        """
        Get statistics for a video.

        Returns:
            dict with views, likes, comments, or None if video not found.
        """
        try:
            data = self._make_request("videos", {
                "part": "statistics",
                "id": video_id,
            })

            if not data.get("items"):
                return None

            stats = data["items"][0]["statistics"]

            return {
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
            }

        except httpx.HTTPStatusError as e:
            raise YouTubeAPIError(f"HTTP error fetching video stats: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Error fetching video stats: {e}")

    def get_video_details(self, video_id: str) -> Optional[dict]:
        """
        Get full details for a video (snippet + content details + statistics).

        Returns:
            dict with title, published_at, duration_seconds, views, likes, comments
            or None if video not found.
        """
        try:
            data = self._make_request("videos", {
                "part": "snippet,contentDetails,statistics",
                "id": video_id,
            })

            if not data.get("items"):
                return None

            item = data["items"][0]
            snippet = item["snippet"]
            content = item["contentDetails"]
            stats = item["statistics"]

            return {
                "video_id": video_id,
                "channel_id": snippet["channelId"],
                "title": snippet["title"],
                "published_at": snippet["publishedAt"],
                "duration_seconds": self._parse_duration(content["duration"]),
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
            }

        except httpx.HTTPStatusError as e:
            raise YouTubeAPIError(f"HTTP error fetching video details: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Error fetching video details: {e}")

    def get_channel_info(self, channel_id: str) -> Optional[dict]:
        """
        Get channel information.

        Returns:
            dict with channel_id, channel_name, subscriber_count, total_videos
            or None if channel not found.
        """
        try:
            data = self._make_request("channels", {
                "part": "snippet,statistics",
                "id": channel_id,
            })

            if not data.get("items"):
                return None

            item = data["items"][0]
            snippet = item["snippet"]
            stats = item["statistics"]

            return {
                "channel_id": channel_id,
                "channel_name": snippet["title"],
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "total_videos": int(stats.get("videoCount", 0)),
            }

        except httpx.HTTPStatusError as e:
            raise YouTubeAPIError(f"HTTP error fetching channel info: {e}")
        except Exception as e:
            raise YouTubeAPIError(f"Error fetching channel info: {e}")

    def resolve_channel_url(self, url: str) -> Optional[dict]:
        """
        Resolve any YouTube channel URL to channel info.

        Accepts:
        - youtube.com/@handle
        - youtube.com/channel/UCxxx
        - youtube.com/c/CustomName
        - @handle
        - UCxxx

        Returns:
            dict with channel_id, channel_name, subscriber_count, total_videos
            or None if channel not found.
        """
        parsed = parse_channel_url(url)

        if parsed['type'] == 'channel_id':
            # Direct channel ID - just fetch info
            return self.get_channel_info(parsed['value'])

        elif parsed['type'] == 'handle':
            # Resolve handle using forHandle parameter
            return self._resolve_by_handle(parsed['value'])

        elif parsed['type'] == 'user':
            # Resolve legacy username
            return self._resolve_by_username(parsed['value'])

        elif parsed['type'] == 'custom':
            # Try handle first, then search
            result = self._resolve_by_handle(parsed['value'])
            if result:
                return result
            return self._resolve_by_search(parsed['value'])

        return None

    def _resolve_by_handle(self, handle: str) -> Optional[dict]:
        """Resolve a channel handle (@name) to channel info."""
        try:
            data = self._make_request("channels", {
                "part": "snippet,statistics",
                "forHandle": handle,
            })

            if not data.get("items"):
                return None

            item = data["items"][0]
            snippet = item["snippet"]
            stats = item["statistics"]

            return {
                "channel_id": item["id"],
                "channel_name": snippet["title"],
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "total_videos": int(stats.get("videoCount", 0)),
            }

        except Exception:
            return None

    def _resolve_by_username(self, username: str) -> Optional[dict]:
        """Resolve a legacy username to channel info."""
        try:
            data = self._make_request("channels", {
                "part": "snippet,statistics",
                "forUsername": username,
            })

            if not data.get("items"):
                return None

            item = data["items"][0]
            snippet = item["snippet"]
            stats = item["statistics"]

            return {
                "channel_id": item["id"],
                "channel_name": snippet["title"],
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "total_videos": int(stats.get("videoCount", 0)),
            }

        except Exception:
            return None

    def _resolve_by_search(self, query: str) -> Optional[dict]:
        """Last resort: search for a channel by name."""
        try:
            data = self._make_request("search", {
                "part": "snippet",
                "q": query,
                "type": "channel",
                "maxResults": 1,
            })

            if not data.get("items"):
                return None

            item = data["items"][0]
            channel_id = item["snippet"]["channelId"]

            # Now get full channel info
            return self.get_channel_info(channel_id)

        except Exception:
            return None

    def _parse_duration(self, duration: str) -> int:
        """
        Parse ISO 8601 duration to seconds.
        Example: PT1H30M15S -> 5415 seconds
        """
        import re

        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds


class YouTubeAPIError(Exception):
    """Custom exception for YouTube API errors."""
    pass
