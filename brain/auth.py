# ============================================
# CHAMP V3 — Authentication Middleware
# Supabase JWT validation + service key auth
# Two paths:
#   1. Web clients: Bearer <supabase_jwt>
#   2. Agent/service: X-API-Key header
# ============================================

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from brain.config import Settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """
    Extract and validate user identity.

    Auth paths (checked in order):
    1. Bearer token (Supabase JWT from web clients)
    2. X-API-Key header (service-to-service from LiveKit agent)

    Returns user_id string.
    Raises 401 if neither is valid.
    """
    settings: Settings = request.app.state.settings

    # --- Path 1: Supabase JWT ---
    if credentials and credentials.credentials:
        token = credentials.credentials
        user_id = await _validate_supabase_jwt(settings, token)
        if user_id:
            return user_id

    # --- Path 2: Service API Key ---
    api_key = request.headers.get("x-api-key", "")
    if api_key and settings.champ_service_key and api_key == settings.champ_service_key:
        # Service calls can pass user_id in header or body
        service_user = request.headers.get("x-user-id", "")
        if service_user:
            return service_user
        # Default service identity
        return "service"

    raise HTTPException(
        status_code=401,
        detail="Missing or invalid authentication. Provide Bearer token or X-API-Key.",
    )


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """
    Same as get_current_user but returns None instead of raising 401.
    Used for endpoints that work with or without auth (e.g., health).
    """
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


async def _validate_supabase_jwt(settings: Settings, token: str) -> Optional[str]:
    """
    Validate a Supabase JWT by calling supabase.auth.get_user(token).
    Returns user_id (UUID string) if valid, None otherwise.
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        logger.warning("Supabase credentials not configured — JWT validation skipped")
        return None

    try:
        from supabase._async.client import create_client as create_async_client

        client = await create_async_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )
        user_response = await client.auth.get_user(token)
        if user_response and user_response.user:
            user_id = user_response.user.id
            logger.debug(f"JWT validated for user: {user_id}")
            return user_id
    except Exception as e:
        logger.debug(f"JWT validation failed: {e}")

    return None
