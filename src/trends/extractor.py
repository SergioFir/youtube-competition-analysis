"""
Topic Extractor.
Uses AI (via OpenRouter) to extract specific topics from video content.
"""

from typing import Optional
from openai import OpenAI
from loguru import logger

from src.config import Config


# Initialize OpenAI client pointing to OpenRouter
_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """Get or create OpenRouter client."""
    global _client
    if _client is None:
        if not Config.OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not configured")
        _client = OpenAI(
            api_key=Config.OPENROUTER_API_KEY,
            base_url=Config.OPENROUTER_BASE_URL,
        )
    return _client


EXTRACTION_PROMPT = """You are a YouTube content analyst. Extract 1-3 specific topics from this video.

Rules:
- Be SPECIFIC, not generic (e.g., "ChatGPT prompt engineering" not "AI")
- Focus on the main actionable topic viewers would search for
- Use lowercase, keep it concise (2-5 words per topic)
- Return ONLY the topics, one per line, nothing else

Example outputs:
chatgpt prompt engineering
midjourney v6 tutorial
how to grow on youtube shorts

Video content:
{content}

Topics (1-3 lines):"""


def extract_topics(content: str) -> list[str]:
    """
    Extract topics from video content using AI.

    Args:
        content: Video content (title + transcript or description)

    Returns:
        List of 1-3 specific topics.
    """
    if not content.strip():
        return []

    try:
        client = get_client()

        response = client.chat.completions.create(
            model=Config.OPENROUTER_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACTION_PROMPT.format(content=content[:4000])  # Limit input
                }
            ],
            max_tokens=100,
            temperature=0.3,  # Lower = more consistent
        )

        # Parse response
        result = response.choices[0].message.content.strip()

        # Split into lines and clean up
        topics = []
        for line in result.split('\n'):
            topic = line.strip().lower()
            # Skip empty lines and numbering
            if topic and not topic[0].isdigit():
                # Remove common prefixes like "- " or "* "
                if topic.startswith(('-', '*', '•')):
                    topic = topic[1:].strip()
                if topic:
                    topics.append(topic)

        # Limit to 3 topics
        topics = topics[:3]

        logger.debug(f"Extracted topics: {topics}")
        return topics

    except Exception as e:
        logger.error(f"Error extracting topics: {e}")
        return []


def extract_topics_for_video(
    video_id: str,
    title: str,
    description: str,
) -> list[str]:
    """
    Extract topics for a video (fetches transcript automatically).

    Args:
        video_id: YouTube video ID
        title: Video title
        description: Video description

    Returns:
        List of topics.
    """
    from src.trends.transcript import get_video_content

    content = get_video_content(video_id, title, description)
    return extract_topics(content)
