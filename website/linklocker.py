"""
Link Locker integration — wraps whichever "complete a task to unlock" ad
service you sign up with (GPLinks, Linkvertise, Lootlabs, etc.).

Default request format here matches GPLinks' simple GET-based API. Every
provider's API is a little different — if you use a different one, check
ITS docs and adjust `create_locked_link()` below (usually just the base
URL and the JSON field name for the resulting link change).

If LINKLOCKER_API_KEY is not set, this is skipped entirely and the raw
destination URL is returned instead — so the trial flow still works for
testing without a locker account.
"""
import logging
import requests

import config

log = logging.getLogger("hosting-bot")


def create_locked_link(destination_url: str) -> str:
    """Returns a locker URL that redirects to `destination_url` only after
    the user completes the provider's task/ad-wall. Falls back to the raw
    destination_url if no locker is configured or the API call fails —
    NEVER blocks the whole trial flow just because the locker is down."""
    if not config.LINKLOCKER_ENABLED:
        return destination_url

    try:
        resp = requests.get(
            config.LINKLOCKER_API_BASE,
            params={"api": config.LINKLOCKER_API_KEY, "url": destination_url},
            timeout=10,
        )
        data = resp.json()
        # GPLinks-style response: {"status": "success", "shortenedUrl": "..."}
        if data.get("status") == "success" and data.get("shortenedUrl"):
            return data["shortenedUrl"]
        log.error(f"Link locker API returned no shortened URL: {data}")
    except Exception as e:
        log.error(f"Link locker API call failed: {e}")

    # graceful fallback — don't let a broken locker integration block trials
    return destination_url
