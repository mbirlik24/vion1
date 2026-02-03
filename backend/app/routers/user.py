from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import List
# Rate limiting temporarily disabled
# from slowapi import Limiter
# from slowapi.util import get_remote_address

from app.services.auth import get_current_user
from app.services.supabase_client import get_user_credits

router = APIRouter()


class BalanceResponse(BaseModel):
    credits: float


class PricingPlan(BaseModel):
    id: str
    name: str
    credits: int
    price: float
    description: str
    features: List[str]
    popular: bool = False


class PricingResponse(BaseModel):
    plans: List[PricingPlan]


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(request: Request, user: dict = Depends(get_current_user)):
    """Get the current user's credit balance."""
    credits = await get_user_credits(user["id"])
    return {"credits": credits}


@router.get("/me")
async def get_current_user_info(request: Request, user: dict = Depends(get_current_user)):
    """Get current user information."""
    credits = await get_user_credits(user["id"])
    return {
        "id": user["id"],
        "email": user["email"],
        "credits": credits,
    }


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing(request: Request):
    """Get available pricing plans."""
    plans = [
        PricingPlan(
            id="starter",
            name="Starter",
            credits=1000,
            price=5.0,
            description="Perfect for trying out Chatow",
            features=[
                "1,000 credits",
                "Fast & Pro mode access",
                "Smart model routing",
                "Email support",
            ],
        ),
        PricingPlan(
            id="pro",
            name="Pro",
            credits=5000,
            price=20.0,
            description="Best for regular users",
            features=[
                "5,000 credits",
                "Fast & Pro mode access",
                "Smart model routing",
                "Priority support",
                "Better value per credit",
            ],
            popular=True,
        ),
        PricingPlan(
            id="unlimited",
            name="Unlimited",
            credits=25000,
            price=80.0,
            description="For power users",
            features=[
                "25,000 credits",
                "Fast & Pro mode access",
                "Smart model routing",
                "Priority support",
                "Best value per credit",
            ],
        ),
    ]
    return {"plans": plans}
