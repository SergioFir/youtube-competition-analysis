"""
Supabase client connection.
"""

from supabase import create_client, Client
from src.config import Config

# Global client instance (lazy initialization)
_client: Client | None = None


def get_client() -> Client:
    """
    Get the Supabase client instance.
    Creates it on first call, reuses afterwards.
    """
    global _client

    if _client is None:
        if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in environment")

        _client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

    return _client


# Convenience alias
supabase = get_client
