"""
Transcript fetcher.
Uses youtube-transcript-api to get video transcripts, falls back to title+description.
"""

from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from loguru import logger


def get_transcript(video_id: str, max_length: int = 5000) -> Optional[str]:
    """
    Fetch transcript for a YouTube video.

    Args:
        video_id: YouTube video ID
        max_length: Maximum transcript length (truncates if longer)

    Returns:
        Transcript text, or None if unavailable.
    """
    try:
        # New API (v1.x) uses instance methods
        api = YouTubeTranscriptApi()

        # Fetch transcript (tries English first)
        transcript_data = api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])

        # Combine all text segments
        full_text = " ".join(segment.text for segment in transcript_data)

        # Clean up
        full_text = full_text.replace('\n', ' ').strip()

        # Truncate if too long
        if len(full_text) > max_length:
            full_text = full_text[:max_length] + "..."

        logger.debug(f"Fetched transcript for {video_id}: {len(full_text)} chars")
        return full_text

    except Exception as e:
        # Catch all transcript errors (disabled, not found, unavailable, etc.)
        logger.debug(f"No transcript for {video_id}: {e}")
        return None


def get_video_content(video_id: str, title: str, description: str) -> str:
    """
    Get content for topic extraction.
    Tries transcript first, falls back to title + description.

    Args:
        video_id: YouTube video ID
        title: Video title
        description: Video description

    Returns:
        Content string for AI analysis.
    """
    # Try to get transcript
    transcript = get_transcript(video_id)

    if transcript:
        # Use transcript with title for context
        return f"Title: {title}\n\nTranscript: {transcript}"
    else:
        # Fallback to title + description
        # Truncate description if too long
        desc = description[:2000] if description else ""
        return f"Title: {title}\n\nDescription: {desc}"
