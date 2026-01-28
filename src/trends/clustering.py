"""
Topic Clustering.
Uses AI to group similar topics into clusters.
"""

from typing import Optional
from openai import OpenAI
from loguru import logger

from src.config import Config
from src.trends.extractor import get_client


CLUSTERING_PROMPT = """You are a content analyst. Group these YouTube video topics into clusters of similar topics.

Rules:
- Group topics that are essentially about the same thing
- Create a normalized name for each cluster (2-5 words, lowercase)
- Only create clusters for topics that have at least 2 similar items
- Single unique topics should be their own cluster
- Be specific with cluster names

Input topics:
{topics}

Output format (JSON):
{{
  "clusters": [
    {{
      "name": "normalized cluster name",
      "topics": ["original topic 1", "original topic 2"]
    }}
  ]
}}

Return ONLY valid JSON, no markdown or explanation."""


def cluster_topics(topics: list[str]) -> dict:
    """
    Group similar topics into clusters using AI.

    Args:
        topics: List of raw topic strings

    Returns:
        Dict with 'clusters' list, each containing 'name' and 'topics'.
    """
    if not topics:
        return {"clusters": []}

    # Deduplicate while preserving order
    unique_topics = list(dict.fromkeys(topics))

    if len(unique_topics) <= 1:
        # Single topic = single cluster
        if unique_topics:
            return {"clusters": [{"name": unique_topics[0], "topics": unique_topics}]}
        return {"clusters": []}

    try:
        client = get_client()

        # Format topics as a list
        topics_text = "\n".join(f"- {t}" for t in unique_topics)

        response = client.chat.completions.create(
            model=Config.OPENROUTER_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": CLUSTERING_PROMPT.format(topics=topics_text)
                }
            ],
            max_tokens=1000,
            temperature=0.2,  # Lower = more consistent
        )

        result = response.choices[0].message.content.strip()

        # Try to parse JSON
        import json

        # Clean up potential markdown code blocks
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
            result = result.strip()

        data = json.loads(result)

        # Validate structure
        if "clusters" not in data:
            raise ValueError("Missing 'clusters' key in response")

        # Ensure all original topics are accounted for
        clustered_topics = set()
        for cluster in data["clusters"]:
            if "name" not in cluster or "topics" not in cluster:
                continue
            clustered_topics.update(cluster["topics"])

        # Add any missing topics as their own clusters
        for topic in unique_topics:
            if topic not in clustered_topics:
                data["clusters"].append({
                    "name": topic,
                    "topics": [topic]
                })

        logger.debug(f"Created {len(data['clusters'])} clusters from {len(unique_topics)} topics")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse clustering response as JSON: {e}")
        # Fallback: each topic is its own cluster
        return {
            "clusters": [{"name": t, "topics": [t]} for t in unique_topics]
        }
    except Exception as e:
        logger.error(f"Error clustering topics: {e}")
        # Fallback: each topic is its own cluster
        return {
            "clusters": [{"name": t, "topics": [t]} for t in unique_topics]
        }
