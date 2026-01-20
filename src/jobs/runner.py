"""
Job runner.
Coordinates all periodic jobs using the schedule library.
"""

import time
import schedule
from loguru import logger

from src.config import Config
from src.discovery.polling import PollingDiscovery
from src.scheduler.snapshot_worker import SnapshotWorker
from src.database.baselines import update_all_baselines_for_channel
from src.database.channels import get_active_channels


class JobRunner:
    """
    Runs all periodic jobs on their configured schedules.
    """

    def __init__(self):
        self.discovery = PollingDiscovery()
        self.snapshot_worker = SnapshotWorker()

    def setup_schedules(self):
        """Configure all job schedules."""

        # Polling discovery - check for new videos
        schedule.every(Config.POLLING_INTERVAL_MINUTES).minutes.do(
            self._run_discovery
        )

        # Snapshot worker - process pending snapshots
        schedule.every(Config.SNAPSHOT_WORKER_INTERVAL_MINUTES).minutes.do(
            self._run_snapshot_worker
        )

        # Baseline calculator - update channel baselines
        schedule.every(Config.BASELINE_UPDATE_HOURS).hours.do(
            self._run_baseline_calculator
        )

        # Video completion check - backup cleanup
        schedule.every(1).hours.do(
            self._run_completion_check
        )

        logger.info("Job schedules configured:")
        logger.info(f"  - Discovery: every {Config.POLLING_INTERVAL_MINUTES} minutes")
        logger.info(f"  - Snapshots: every {Config.SNAPSHOT_WORKER_INTERVAL_MINUTES} minutes")
        logger.info(f"  - Baselines: every {Config.BASELINE_UPDATE_HOURS} hours")
        logger.info(f"  - Completion check: every 1 hour")

    def _run_discovery(self):
        """Run video discovery job."""
        logger.info("Running discovery job...")
        try:
            summary = self.discovery.poll_all_channels()
            logger.info(f"Discovery complete: {summary}")
        except Exception as e:
            logger.error(f"Discovery job failed: {e}")

    def _run_snapshot_worker(self):
        """Run snapshot worker job."""
        logger.debug("Running snapshot worker...")
        try:
            summary = self.snapshot_worker.process_pending_snapshots()
            if summary["processed"] > 0:
                logger.info(f"Snapshots processed: {summary}")
        except Exception as e:
            logger.error(f"Snapshot worker failed: {e}")

    def _run_baseline_calculator(self):
        """Run baseline calculation job."""
        logger.info("Running baseline calculator...")
        try:
            channels = get_active_channels()
            for channel in channels:
                result = update_all_baselines_for_channel(channel["channel_id"])
                if result["updated"]:
                    logger.info(f"Updated baselines for {channel['channel_name']}: {result['updated']}")
        except Exception as e:
            logger.error(f"Baseline calculator failed: {e}")

    def _run_completion_check(self):
        """Run video completion check."""
        try:
            count = self.snapshot_worker.check_and_complete_videos()
            if count > 0:
                logger.info(f"Marked {count} videos as completed")
        except Exception as e:
            logger.error(f"Completion check failed: {e}")

    def run_once(self):
        """Run all jobs once immediately (for testing)."""
        logger.info("Running all jobs once...")
        self._run_discovery()
        self._run_snapshot_worker()
        self._run_baseline_calculator()
        self._run_completion_check()
        logger.info("All jobs completed")

    def run_forever(self):
        """Run the scheduler loop forever."""
        self.setup_schedules()

        # Run discovery and snapshots immediately on start
        self._run_discovery()
        self._run_snapshot_worker()

        logger.info("Starting scheduler loop...")
        while True:
            schedule.run_pending()
            time.sleep(10)  # Check every 10 seconds
