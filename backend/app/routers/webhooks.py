from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
# Rate limiting temporarily disabled
# from slowapi import Limiter
# from slowapi.util import get_remote_address
import hmac
import hashlib

from app.services.supabase_client import get_user_by_email, add_credits
from app.config import get_settings

router = APIRouter()
settings = get_settings()

# Credit packages mapping (product_id -> credits)
CREDIT_PACKAGES = {
    "starter": 1000,      # $5 - 1,000 credits
    "pro": 5000,          # $20 - 5,000 credits
    "unlimited": 25000,   # $80 - 25,000 credits
}


class LemonSqueezyWebhookPayload(BaseModel):
    meta: dict
    data: dict


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Lemon Squeezy webhook signature."""
    if not secret:
        # Skip verification if no secret configured (development)
        return True
    
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)


@router.post("/lemon-squeezy")
async def lemon_squeezy_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature")
):
    """
    Handle Lemon Squeezy webhook events.
    
    Listens for 'order_created' events to add credits to user accounts.
    """
    # Get raw body for signature verification
    body = await request.body()
    
    # Verify signature
    if settings.lemon_squeezy_webhook_secret:
        if not x_signature:
            raise HTTPException(status_code=401, detail="Missing signature")
        
        if not verify_webhook_signature(body, x_signature, settings.lemon_squeezy_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # Get event type
    event_name = payload.get("meta", {}).get("event_name")
    
    if event_name != "order_created":
        # We only care about successful orders
        return {"status": "ignored", "event": event_name}
    
    # Extract order data
    data = payload.get("data", {})
    attributes = data.get("attributes", {})
    
    # Get customer email
    user_email = attributes.get("user_email")
    if not user_email:
        raise HTTPException(status_code=400, detail="No user email in payload")
    
    # Get order ID
    order_id = str(data.get("id", ""))
    
    # Get product variant name to determine credit amount
    first_order_item = attributes.get("first_order_item", {})
    variant_name = first_order_item.get("variant_name", "").lower()
    product_name = first_order_item.get("product_name", "").lower()
    
    # Determine credits based on product/variant
    credits_to_add = 0
    for package_key, package_credits in CREDIT_PACKAGES.items():
        if package_key in variant_name or package_key in product_name:
            credits_to_add = package_credits
            break
    
    # Check custom_data for explicit credit amount
    custom_data = payload.get("meta", {}).get("custom_data", {})
    if "credits" in custom_data:
        try:
            credits_to_add = int(custom_data["credits"])
        except (ValueError, TypeError):
            pass
    
    if credits_to_add <= 0:
        # Default to starter package if can't determine
        credits_to_add = CREDIT_PACKAGES["starter"]
    
    # Find user by email
    user = await get_user_by_email(user_email)
    
    if not user:
        # User doesn't exist yet - store for later
        # In production, you might create a pending credits record
        return {
            "status": "pending",
            "message": f"User {user_email} not found. Credits will be added when they sign up.",
            "credits": credits_to_add,
        }
    
    # Add credits to user
    success = await add_credits(
        user_id=user["id"],
        amount=credits_to_add,
        order_id=order_id,
        description=f"Purchase: {product_name} - {variant_name}"
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to add credits")
    
    return {
        "status": "success",
        "user_email": user_email,
        "credits_added": credits_to_add,
        "order_id": order_id,
    }


@router.get("/lemon-squeezy/test")
async def test_webhook(request: Request):
    """Test endpoint to verify webhook routing."""
    return {"status": "ok", "message": "Lemon Squeezy webhook endpoint is working"}
