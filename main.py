"""
YouTube Competition Analysis - Main Entry Point

Usage:
    python main.py                  # Run the scheduler (main mode)
    python main.py --once           # Run all jobs once (testing)
    python main.py --add-channel    # Add a channel interactively
    python main.py --list-channels  # List tracked channels
    python main.py --test           # Test connection and configuration
"""

import sys
from loguru import logger

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


def test_connection():
    """Test Supabase and YouTube API connections."""
    from src.config import Config
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


def run_scheduler():
    """Run the main scheduler loop."""
    from src.jobs.runner import JobRunner

    print("\n=== YouTube Competition Analysis ===\n")
    print("Starting scheduler...")
    print("Press Ctrl+C to stop.\n")

    runner = JobRunner()

    try:
        runner.run_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down...")


def run_once():
    """Run all jobs once (for testing)."""
    from src.jobs.runner import JobRunner

    print("\n=== Running All Jobs Once ===\n")

    runner = JobRunner()
    runner.run_once()


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
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
