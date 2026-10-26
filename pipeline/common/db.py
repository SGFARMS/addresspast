"""Supabase client (service role). Server/CI only — never ship this key to a browser."""
from functools import lru_cache

from supabase import Client, create_client

from .config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


@lru_cache(maxsize=1)
def db() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


_TRANSIENT = ("Server disconnected", "Connection refused", "connection error", "terminating connection",
              "timed out", "ReadTimeout", "ConnectError", "RemoteProtocolError", "PGRST000", "57P01", "503", "502")


def retry(fn, attempts: int = 4):
    """Run fn(); on a dropped connection or a database restart, wait and try again (2 s, 5 s, 15 s)."""
    import time

    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # httpx / postgrest errors; only transient-looking ones are retried
            text = f"{type(e).__name__}: {e}"
            if i == attempts - 1 or not any(t in text for t in _TRANSIENT):
                raise
            time.sleep((2, 5, 15)[min(i, 2)])
