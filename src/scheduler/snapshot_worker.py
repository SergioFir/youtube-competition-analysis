"""
Snapshot worker.
Processes scheduled snapshots that are due.
"""

from loguru import logger

from src.database.snapshots import (
    get_pending_scheduled_snapshots,
    add_snapshot,
    mark_scheduled_snapshot_completed,
    mark_scheduled_snapshot_failed,
)
from src.database.videos import mark_video_completed, get_video
from src.youtube.api import YouTubeAPI, YouTubeAPIError


class SnapshotWorker:
    """
    Worker that processes scheduled snapshots.
    Should be run periodically (every 1-5 minutes).
    """

    def __init__(self):
        self.youtube_api = YouTubeAPI()

    def process_pending_snapshots(self, limit: int = 100) -> dict:
        """
        Process all pending scheduled snapshots that are due.

        Returns:
            Summary dict with processed, succeeded, failed counts.
        """
        pending = get_pending_scheduled_snapshots(limit=limit)
        summary = {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
        }

        for scheduled in pending:
            summary["processed"] += 1
            success = self._process_single_snapshot(scheduled)

            if success:
                summary["succeeded"] += 1
            else:
                summary["failed"] += 1

        return summary

    def _process_single_snapshot(self, scheduled: dict) -> bool:
        """
        Process a single scheduled snapshot.

        Args:
            scheduled: Scheduled snapshot record (includes joined video data)

        Returns:
            True if successful, False otherwise.
        """
        scheduled_id = scheduled["id"]
        video_id = scheduled["video_id"]
        window_type = scheduled["window_type"]

        try:
            # Fetch current stats from YouTube
            stats = self.youtube_api.get_video_stats(video_id)

            if stats is None:
                # Video might have been deleted
                logger.warning(f"Video {video_id} not found on YouTube")
                mark_scheduled_snapshot_failed(scheduled_id, "Video not found on YouTube")
                return False

            # Save the snapshot
            add_snapshot(
                video_id=video_id,
                window_type=window_type,
                views=stats["views"],
                likes=stats["likes"],
                comments=stats["comments"],
            )

            # Mark scheduled snapshot as completed
            mark_scheduled_snapshot_completed(scheduled_id)

            logger.info(f"Snapshot {window_type} for {video_id}: {stats['views']} views")

            # If this was the final snapshot (14d), mark video as completed
            if window_type == "14d":
                mark_video_completed(video_id)
                logger.info(f"Video {video_id} tracking completed")

            return True

        except YouTubeAPIError as e:
            error_msg = str(e)
            logger.error(f"API error for {video_id} ({window_type}): {error_msg}")
            mark_scheduled_snapshot_failed(scheduled_id, error_msg)
            return False

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing snapshot for {video_id}: {error_msg}")
            mark_scheduled_snapshot_failed(scheduled_id, error_msg)
            return False

    def check_and_complete_videos(self) -> int:
        """
        Check for videos that should be marked as completed.
        This is a backup in case the 14d snapshot completion was missed.

        Returns:
            Number of videos marked as completed.
        """
        from datetime import datetime
        from src.database.videos import get_active_videos

        completed_count = 0
        now = datetime.utcnow()

        for video in get_active_videos():
            tracking_until = video.get("tracking_until")
            if tracking_until:
                # Parse the tracking_until timestamp
                if isinstance(tracking_until, str):
                    tracking_until = datetime.fromisoformat(tracking_until.replace("Z", "+00:00"))

                # Remove timezone info for comparison
                if tracking_until.tzinfo:
                    tracking_until = tracking_until.replace(tzinfo=None)

                if now > tracking_until:
                    mark_video_completed(video["video_id"])
                    logger.info(f"Video {video['video_id']} marked as completed (past tracking_until)")
                    completed_count += 1

        return completed_count
