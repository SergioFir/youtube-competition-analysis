"""
Trend Detection Module.
Detects hot topics across multiple channels.
"""

from src.trends.transcript import get_transcript, get_video_content
from src.trends.extractor import extract_topics, extract_topics_for_video
from src.trends.clustering import cluster_topics

__all__ = [
    "get_transcript",
    "get_video_content",
    "extract_topics",
    "extract_topics_for_video",
    "cluster_topics",
]
