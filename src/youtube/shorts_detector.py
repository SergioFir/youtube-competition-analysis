"""
YouTube Shorts detection.
Uses the URL check method to reliably determine if a video is a Short.
"""

import httpx


def is_youtube_short(video_id: str) -> bool:
    """
    Check if a video is a YouTube Short.

    Method: Try to access youtube.com/shorts/{video_id}
    If it returns 200, it's a Short.
    If it redirects to /watch, it's a regular video.

    Args:
        video_id: The YouTube video ID

    Returns:
        True if the video is a Short, False otherwise.
    """
    url = f"https://www.youtube.com/shorts/{video_id}"

    try:
        with httpx.Client(follow_redirects=False) as client:
            response = client.head(url, timeout=10)

            # 200 = Short exists at this URL
            # 303 or other redirect = Not a Short (redirects to /watch)
            if response.status_code == 200:
                return True

            # Sometimes YouTube returns 303 redirect for non-Shorts
            if response.status_code in (301, 302, 303, 307, 308):
                return False

            # For other status codes, try GET request
            response = client.get(url, timeout=10, follow_redirects=False)
            return response.status_code == 200

    except httpx.RequestError:
        # On network error, return None or default to False
        # We'll mark is_short as None in the database for retry
        return False


def detect_short_with_fallback(video_id: str, duration_seconds: int = None) -> bool | None:
    """
    Detect if video is a Short, with fallback to duration heuristic.

    Args:
        video_id: The YouTube video ID
        duration_seconds: Video duration (optional fallback)

    Returns:
        True/False if determined, None if uncertain.
    """
    try:
        return is_youtube_short(video_id)
    except Exception:
        # Fallback: if we have duration and it's <= 180 seconds, assume Short
        if duration_seconds is not None and duration_seconds <= 180:
            return True
        return None
