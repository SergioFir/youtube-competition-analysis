"""
YouTube Competition Analysis - Main Entry Point

Usage:
    python main.py                  # Run the web server with scheduler (production)
    python main.py --once           # Run all jobs once (testing)
    python main.py --add-channel    # Add a channel interactively
    python main.py --list-channels  # List tracked channels
    python main.py --test           # Test connection and configuration
    python main.py --subscribe-all  # Subscribe all channels to WebSub
"""

import sys
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, Response, Query
from loguru import logger
import uvicorn

from src.config import Config

# Configure logging
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
)
logger.add(
    "logs/youtube_tracker.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
)


# Background scheduler task
async def run_scheduler_background():
    """Run the scheduler in the background."""
    import time
    import schedule
    from src.discovery.polling import PollingDiscovery
    from src.discovery.websub import renew_expiring_subscriptions
    from src.scheduler.snapshot_worker import SnapshotWorker
    from src.database.baselines import update_all_baselines_for_channel
    from src.database.channels import get_active_channels

    discovery = PollingDiscovery()
    snapshot_worker = SnapshotWorker()

    def run_discovery():
        logger.info("Running discovery job...")
        try:
            summary = discovery.poll_all_channels()
            logger.info(f"Discovery complete: {summary}")
        except Exception as e:
            logger.error(f"Discovery job failed: {e}")

    def run_snapshot_worker():
        logger.debug("Running snapshot worker...")
        try:
            summary = snapshot_worker.process_pending_snapshots()
            if summary["processed"] > 0:
                logger.info(f"Snapshots processed: {summary}")
        except Exception as e:
            logger.error(f"Snapshot worker failed: {e}")

    def run_baseline_calculator():
        logger.info("Running baseline calculator...")
        try:
            channels = get_active_channels()
            for channel in channels:
                result = update_all_baselines_for_channel(channel["channel_id"])
                if result["updated"]:
                    logger.info(f"Updated baselines for {channel['channel_name']}: {result['updated']}")
        except Exception as e:
            logger.error(f"Baseline calculator failed: {e}")

    def run_completion_check():
        try:
            count = snapshot_worker.check_and_complete_videos()
            if count > 0:
                logger.info(f"Marked {count} videos as completed")
        except Exception as e:
            logger.error(f"Completion check failed: {e}")

    def run_websub_renewal():
        """Renew expiring WebSub subscriptions."""
        if Config.DISCOVERY_MODE == "websub":
            logger.info("Running WebSub renewal check...")
            try:
                summary = renew_expiring_subscriptions()
                logger.info(f"WebSub renewal complete: {summary}")
            except Exception as e:
                logger.error(f"WebSub renewal failed: {e}")

    # Set up schedules based on discovery mode
    if Config.DISCOVERY_MODE == "polling":
        schedule.every(Config.POLLING_INTERVAL_MINUTES).minutes.do(run_discovery)
        logger.info(f"Polling discovery: every {Config.POLLING_INTERVAL_MINUTES} minutes")
    else:
        # In WebSub mode, still poll occasionally as a fallback
        schedule.every(60).minutes.do(run_discovery)
        logger.info("WebSub mode: fallback polling every 60 minutes")
        # Renew subscriptions daily
        schedule.every(24).hours.do(run_websub_renewal)
        logger.info("WebSub renewal: every 24 hours")

    schedule.every(Config.SNAPSHOT_WORKER_INTERVAL_MINUTES).minutes.do(run_snapshot_worker)
    schedule.every(Config.BASELINE_UPDATE_HOURS).hours.do(run_baseline_calculator)
    schedule.every(1).hours.do(run_completion_check)

    logger.info(f"Snapshots: every {Config.SNAPSHOT_WORKER_INTERVAL_MINUTES} minutes")
    logger.info(f"Baselines: every {Config.BASELINE_UPDATE_HOURS} hours")
    logger.info(f"Completion check: every 1 hour")

    # Run discovery and snapshots immediately on start
    run_discovery()
    run_snapshot_worker()

    # Subscribe to WebSub if in websub mode
    if Config.DISCOVERY_MODE == "websub" and Config.WEBSUB_CALLBACK_URL:
        from src.discovery.websub import subscribe_all_channels
        logger.info("Subscribing all channels to WebSub...")
        summary = subscribe_all_channels()
        logger.info(f"WebSub subscription: {summary}")

    logger.info("Background scheduler started")

    # Run forever
    while True:
        schedule.run_pending()
        await asyncio.sleep(10)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - start/stop background tasks."""
    # Start background scheduler
    scheduler_task = asyncio.create_task(run_scheduler_background())
    logger.info("Application started")

    yield

    # Shutdown
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    logger.info("Application shutdown")


# Create FastAPI app
app = FastAPI(
    title="YouTube Competition Analysis",
    description="Tracks YouTube videos and detects breakout content",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "YouTube Competition Analysis",
        "discovery_mode": Config.DISCOVERY_MODE,
    }


@app.get("/health")
async def health():
    """Health check for Railway."""
    return {"status": "ok"}


@app.get("/webhooks/youtube")
async def websub_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_topic: str = Query(None, alias="hub.topic"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_lease_seconds: Optional[str] = Query(None, alias="hub.lease_seconds"),
):
    """
    Handle WebSub subscription verification.
    YouTube hub sends this to verify we want the subscription.
    """
    from src.discovery.websub import WebSubHandler

    logger.info(f"WebSub verification request: mode={hub_mode}, topic={hub_topic}")

    if not all([hub_mode, hub_topic, hub_challenge]):
        logger.warning("Missing required WebSub verification parameters")
        return Response(content="Missing parameters", status_code=400)

    handler = WebSubHandler()
    result = handler.verify_subscription(
        mode=hub_mode,
        topic=hub_topic,
        challenge=hub_challenge,
        lease_seconds=hub_lease_seconds,
    )

    if result:
        # Must return the challenge as plain text
        return Response(content=result, media_type="text/plain", status_code=200)
    else:
        return Response(content="Verification failed", status_code=404)


@app.post("/webhooks/youtube")
async def websub_notification(request: Request):
    """
    Handle WebSub push notification.
    YouTube sends this when a new video is published.
    """
    from src.discovery.websub import WebSubHandler

    body = await request.body()
    logger.info(f"WebSub notification received ({len(body)} bytes)")

    handler = WebSubHandler()
    summary = handler.handle_notification(body)

    logger.info(f"WebSub notification processed: {summary}")

    # Always return 200 to acknowledge receipt
    return {"status": "received", "summary": summary}


def test_connection():
    """Test Supabase and YouTube API connections."""
    from src.database.connection import get_client
    from src.youtube.api import YouTubeAPI

    print("\n=== Testing Configuration ===\n")

    # Check config
    errors = Config.validate()
    if errors:
        print("Configuration errors:")
        for e in errors:
            print(f"  - {e}")
        return False

    print("Configuration: OK")

    # Test Supabase
    print("\nTesting Supabase connection...")
    try:
        client = get_client()
        result = client.table("channels").select("channel_id").limit(1).execute()
        print(f"Supabase: OK (connected to {Config.SUPABASE_URL})")
    except Exception as e:
        print(f"Supabase: FAILED - {e}")
        return False

    # Test YouTube API
    print("\nTesting YouTube API...")
    try:
        api = YouTubeAPI()
        # Test with a known video (Rick Astley - Never Gonna Give You Up)
        stats = api.get_video_stats("dQw4w9WgXcQ")
        if stats:
            print(f"YouTube API: OK (test video has {stats['views']:,} views)")
        else:
            print("YouTube API: WARNING - Could not fetch test video")
    except Exception as e:
        print(f"YouTube API: FAILED - {e}")
        return False

    print("\n=== All Tests Passed ===\n")
    return True


def add_channel_interactive():
    """Add a channel interactively."""
    from src.database.channels import add_channel, get_channel
    from src.youtube.api import YouTubeAPI

    print("\n=== Add Channel ===\n")

    channel_input = input("Enter YouTube channel URL or @handle: ").strip()

    if not channel_input:
        print("No input provided.")
        return

    # Fetch channel info from YouTube (handles URLs, @handles, and channel IDs)
    print(f"\nResolving channel...")
    api = YouTubeAPI()
    info = api.resolve_channel_url(channel_input)

    if not info:
        print("Could not find channel on YouTube. Check the URL or handle.")
        return

    # Check if already exists
    existing = get_channel(info['channel_id'])
    if existing:
        print(f"Channel already exists: {existing['channel_name']}")
        return

    print(f"\nFound channel:")
    print(f"  Name: {info['channel_name']}")
    print(f"  ID: {info['channel_id']}")
    print(f"  Subscribers: {info['subscriber_count']:,}")
    print(f"  Videos: {info['total_videos']}")

    confirm = input("\nAdd this channel? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    # Add to database
    result = add_channel(
        channel_id=info["channel_id"],
        channel_name=info["channel_name"],
        subscriber_count=info["subscriber_count"],
        total_videos=info["total_videos"],
    )

    if result:
        print(f"\nChannel added successfully!")

        # Subscribe to WebSub if in websub mode
        if Config.DISCOVERY_MODE == "websub" and Config.WEBSUB_CALLBACK_URL:
            from src.discovery.websub import WebSubSubscription
            print("Subscribing to WebSub notifications...")
            sub = WebSubSubscription()
            if sub.subscribe(info["channel_id"]):
                print("WebSub subscription requested!")
            else:
                print("WebSub subscription failed (will use polling fallback)")
    else:
        print(f"\nFailed to add channel.")


def list_channels():
    """List all tracked channels."""
    from src.database.channels import list_channels

    print("\n=== Tracked Channels ===\n")

    channels = list_channels(active_only=False)

    if not channels:
        print("No channels tracked yet. Use --add-channel to add one.")
        return

    for ch in channels:
        status = "ACTIVE" if ch["is_active"] else "PAUSED"
        print(f"[{status}] {ch['channel_name']}")
        print(f"         ID: {ch['channel_id']}")
        print(f"         Subscribers: {ch.get('subscriber_count', 'N/A'):,}")
        print()


def run_once():
    """Run all jobs once (for testing)."""
    from src.jobs.runner import JobRunner

    print("\n=== Running All Jobs Once ===\n")

    runner = JobRunner()
    runner.run_once()


def subscribe_all():
    """Subscribe all channels to WebSub."""
    from src.discovery.websub import subscribe_all_channels

    if not Config.WEBSUB_CALLBACK_URL:
        print("Error: WEBSUB_CALLBACK_URL not configured")
        return

    print("\n=== Subscribing All Channels to WebSub ===\n")
    print(f"Callback URL: {Config.WEBSUB_CALLBACK_URL}")
    print()

    summary = subscribe_all_channels()

    print(f"\nResults:")
    print(f"  Total channels: {summary['total']}")
    print(f"  Subscribed: {summary['subscribed']}")
    print(f"  Failed: {summary['failed']}")


def run_server():
    """Run the FastAPI server."""
    print("\n=== YouTube Competition Analysis ===\n")
    print(f"Starting server on port {Config.PORT}...")
    print(f"Discovery mode: {Config.DISCOVERY_MODE}")
    if Config.DISCOVERY_MODE == "websub":
        print(f"WebSub callback: {Config.WEBSUB_CALLBACK_URL}")
    print()

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=Config.PORT,
        log_level="info",
    )


def main():
    args = sys.argv[1:]

    if "--test" in args:
        test_connection()
    elif "--add-channel" in args:
        add_channel_interactive()
    elif "--list-channels" in args:
        list_channels()
    elif "--once" in args:
        run_once()
    elif "--subscribe-all" in args:
        subscribe_all()
    else:
        run_server()


if __name__ == "__main__":
    main()
