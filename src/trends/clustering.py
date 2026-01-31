"""
Topic Clustering.
Uses AI to group similar topics into clusters.
"""

from typing import Optional
from openai import OpenAI
from loguru import logger

from src.config import Config
from src.trends.extractor import get_client


CLUSTERING_PROMPT = """Group these YouTube video topics into clusters. {context}

Topics:
{topics}

Rules:
1. Group similar topics together
2. Cluster name: 2-5 lowercase words
3. BE SPECIFIC - use actual tool names, product names, or specific techniques
4. AVOID generic names like "ai automation", "ai tools", "productivity tips", "tutorials"
5. Include ALL topics (even unique ones as single-item clusters)

Examples of GOOD cluster names:
- "clawdbot setup tutorials"
- "gemini whisk workflows"
- "antigravity agent building"
- "notebooklm features"
- "claude code tips"

Examples of BAD cluster names (TOO GENERIC - never use these):
- "ai automation"
- "ai tools"
- "productivity"
- "tutorials"
- "google updates"

Return ONLY this JSON format, nothing else:
{{"clusters":[{{"name":"example name","topics":["topic1","topic2"]}}]}}"""


def cluster_topics(topics: list[str], context: str = "") -> dict:
    """
    Group similar topics into clusters using AI.

    Args:
        topics: List of raw topic strings
        context: Optional context about the topics (e.g., bucket name)

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

    import json
    import re

    try:
        client = get_client()

        # Format topics as a list
        topics_text = "\n".join(f"- {t}" for t in unique_topics)

        # Build prompt with optional context
        context_text = f"Context: {context}\n" if context else ""

        def try_parse_response(attempt: int = 1) -> dict:
            response = client.chat.completions.create(
                model=Config.OPENROUTER_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": CLUSTERING_PROMPT.format(context=context_text, topics=topics_text)
                    }
                ],
                max_tokens=2000,
                temperature=0.1,  # Very low for consistency
            )

            result = response.choices[0].message.content.strip()

            # Clean up response
            # Remove markdown code blocks
            if "```" in result:
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', result)
                if match:
                    result = match.group(1)
                else:
                    result = result.replace("```json", "").replace("```", "")

            # Find JSON object
            start = result.find("{")
            end = result.rfind("}") + 1
            if start >= 0 and end > start:
                result = result[start:end]

            result = result.strip()

            return json.loads(result)

        # Try up to 2 times
        try:
            data = try_parse_response(1)
        except json.JSONDecodeError:
            logger.warning("First clustering attempt failed, retrying...")
            try:
                data = try_parse_response(2)
            except json.JSONDecodeError as e:
                raise e

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
