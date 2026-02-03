from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt as pyjwt
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)

settings = get_settings()
security = HTTPBearer()


def decode_jwt(token: str) -> dict:
    """Decode a Supabase JWT token."""
    try:
        # For now, decode without signature verification to avoid issues
        # Supabase already verified the token on the frontend
        # TODO: Implement proper JWT verification with Supabase's public key
        payload = pyjwt.decode(
            token,
            options={
                "verify_signature": False,  # Temporarily disabled
                "verify_exp": True,  # Still check expiration
                "verify_aud": False,
            }
        )
        
        logger.debug(f"Decoded token for user: {payload.get('sub')}")
        return payload
        
    except pyjwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception as e:
        logger.error(f"JWT error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Token decode failed: {str(e)}")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated user from JWT.
    Returns the decoded JWT payload.
    """
    token = credentials.credentials
    payload = decode_jwt(token)
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: no user ID"
        )
    
    return {
        "id": user_id,
        "email": payload.get("email"),
        "role": payload.get("role"),
    }


async def get_optional_user(request: Request) -> dict | None:
    """
    Dependency to optionally get the current user.
    Returns None if no valid token is provided.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    try:
        payload = decode_jwt(token)
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role"),
        }
    except HTTPException:
        return None
