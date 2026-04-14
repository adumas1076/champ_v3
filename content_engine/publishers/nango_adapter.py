"""
Nango OAuth Token Adapter — Fetch tokens from Nango for publishers.

Nango manages OAuth flows, token refresh, and credential storage for 700+ apps.
Instead of raw env vars per platform, publishers call this adapter to get
fresh, auto-refreshed tokens.

Flow:
  Publisher needs token → nango_adapter.get_token("twitter", "influencer_1")
  → Adapter calls Nango API → returns fresh access token
  → If token expired, Nango already refreshed it automatically

Required env vars:
  NANGO_BASE_URL         — Nango server URL (self-hosted or cloud)
  NANGO_SECRET_KEY       — Nango API secret key

Connection IDs follow pattern: {platform}-{influencer_id}
  e.g., "twitter-anthony", "instagram-influencer_1"

See: project_nango_oauth_playbook.md for setup details.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NangoToken:
    """Token data returned from Nango."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[str] = None
    raw: Optional[dict] = None


def _get_nango_config() -> tuple[Optional[str], Optional[str]]:
    """Get Nango connection details from env."""
    return (
        os.getenv("NANGO_BASE_URL", "http://localhost:3003"),
        os.getenv("NANGO_SECRET_KEY"),
    )


async def get_token(
    provider: str,
    influencer_id: str,
    connection_id: Optional[str] = None,
) -> Optional[NangoToken]:
    """Fetch a fresh OAuth token from Nango for a platform + influencer.

    Args:
        provider: Nango provider config key (e.g., "twitter", "instagram", "linkedin")
        influencer_id: Which influencer's account (e.g., "anthony", "influencer_1")
        connection_id: Override the auto-generated connection ID

    Returns:
        NangoToken with fresh access_token, or None if not available.
    """
    base_url, secret_key = _get_nango_config()
    if not secret_key:
        logger.debug(f"[NANGO] No NANGO_SECRET_KEY set — falling back to env vars for {provider}")
        return None

    conn_id = connection_id or f"{provider}-{influencer_id}"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{base_url}/connection/{conn_id}",
                headers={
                    "Authorization": f"Bearer {secret_key}",
                },
                params={
                    "provider_config_key": provider,
                },
            )

            if resp.status_code == 404:
                logger.info(f"[NANGO] No connection found for {conn_id} — needs OAuth setup")
                return None

            resp.raise_for_status()
            data = resp.json()

            credentials = data.get("credentials", {})
            access_token = credentials.get("access_token")

            if not access_token:
                # OAuth1 style (Twitter)
                access_token = credentials.get("oauth_token")

            if not access_token:
                logger.warning(f"[NANGO] No access token in response for {conn_id}")
                return None

            return NangoToken(
                access_token=access_token,
                refresh_token=credentials.get("refresh_token"),
                expires_at=credentials.get("expires_at"),
                raw=credentials,
            )

    except ImportError:
        logger.warning("httpx not installed — run: pip install httpx")
        return None
    except Exception as e:
        logger.warning(f"[NANGO] Failed to fetch token for {conn_id}: {e}")
        return None


async def get_twitter_tokens(influencer_id: str) -> Optional[dict]:
    """Get Twitter OAuth1 tokens (access_token + access_secret).

    Twitter uses OAuth 1.0a which needs both token and secret.
    Nango stores both in the credentials object.
    """
    token = await get_token("twitter", influencer_id)
    if not token or not token.raw:
        return None

    return {
        "access_token": token.raw.get("oauth_token", token.access_token),
        "access_secret": token.raw.get("oauth_token_secret", ""),
    }


async def get_bearer_token(provider: str, influencer_id: str) -> Optional[str]:
    """Get a simple bearer token for platforms using OAuth 2.0.

    Works for: Instagram, LinkedIn, TikTok, YouTube, Facebook.
    """
    token = await get_token(provider, influencer_id)
    if not token:
        return None
    return token.access_token


async def list_connections(provider: Optional[str] = None) -> list[dict]:
    """List all active Nango connections, optionally filtered by provider.

    Useful for: knowing which influencer accounts are connected.
    """
    base_url, secret_key = _get_nango_config()
    if not secret_key:
        return []

    try:
        import httpx

        async with httpx.AsyncClient(timeout=15) as client:
            params = {}
            if provider:
                params["provider_config_key"] = provider

            resp = await client.get(
                f"{base_url}/connections",
                headers={"Authorization": f"Bearer {secret_key}"},
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("connections", [])

    except Exception as e:
        logger.warning(f"[NANGO] Failed to list connections: {e}")
        return []


async def check_connection(provider: str, influencer_id: str) -> bool:
    """Check if an OAuth connection exists and is valid for a platform + influencer."""
    token = await get_token(provider, influencer_id)
    return token is not None and token.access_token is not None