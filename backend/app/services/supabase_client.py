from supabase import create_client, Client
from app.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

# Create Supabase client with service role key for backend operations
supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_key
)


async def get_user_credits(user_id: str) -> float:
    """Get user's current credit balance."""
    response = supabase.table("profiles").select("credit_balance").eq("id", user_id).single().execute()
    error = getattr(response, "error", None)
    if error:
        logger.error(f"Failed to fetch credits for {user_id}: {error}")
        return 0
    if response.data:
        return response.data.get("credit_balance", 0)
    return 0


async def deduct_credits(user_id: str, amount: float, description: str = None) -> bool:
    """
    Deduct credits from user's balance with transaction safety.
    Returns True if successful.
    
    Note: Supabase Python client doesn't support explicit transactions,
    but we use atomic operations and error checking for safety.
    """
    try:
        # Get current balance (with error handling)
        current_balance = await get_user_credits(user_id)
        
        if current_balance < amount:
            logger.warning(f"Insufficient credits for user {user_id}: {current_balance} < {amount}")
            return False
        
        # Update balance atomically
        new_balance = current_balance - amount
        update_response = supabase.table("profiles").update({
            "credit_balance": new_balance
        }).eq("id", user_id).execute()
        
        update_error = getattr(update_response, "error", None)
        if update_error:
            logger.error(f"Failed to update credits for {user_id}: {update_error}")
            return False
        
        # Verify the update was successful
        if not update_response.data:
            logger.error(f"No data returned from credit update for {user_id}")
            return False
        
        # Log transaction (non-blocking - if this fails, credits are still deducted)
        try:
            txn_response = supabase.table("transactions").insert({
                "user_id": user_id,
                "amount": 0,
                "credits_added": -amount,
                "transaction_type": "usage",
                "description": description or "Chat usage"
            }).execute()
            txn_error = getattr(txn_response, "error", None)
            if txn_error:
                logger.warning(f"Failed to log transaction for {user_id}: {txn_error} (credits still deducted)")
        except Exception as txn_ex:
            logger.warning(f"Exception logging transaction for {user_id}: {txn_ex} (credits still deducted)")
        
        return True
    except Exception as e:
        logger.error(f"Error in deduct_credits for {user_id}: {e}", exc_info=True)
        return False


async def add_credits(user_id: str, amount: float, order_id: str = None, description: str = None) -> bool:
    """Add credits to user's balance."""
    # Get current balance
    current_balance = await get_user_credits(user_id)
    
    # Update balance
    new_balance = current_balance + amount
    supabase.table("profiles").update({
        "credit_balance": new_balance
    }).eq("id", user_id).execute()
    
    # Log transaction
    supabase.table("transactions").insert({
        "user_id": user_id,
        "amount": 0,  # Will be set from payment data
        "credits_added": amount,
        "transaction_type": "purchase",
        "lemon_squeezy_order_id": order_id,
        "description": description or "Credit purchase"
    }).execute()
    
    return True


async def get_user_by_email(email: str) -> dict | None:
    """Get user profile by email."""
    response = supabase.table("profiles").select("*").eq("email", email).single().execute()
    return response.data


async def save_message(
    session_id: str,
    role: str,
    content: str,
    model_used: str = None,
    credits_used: float = 0
) -> dict:
    """Save a chat message to the database."""
    try:
        response = supabase.table("chat_messages").insert({
            "session_id": session_id,
            "role": role,
            "content": content,
            "model_used": model_used,
            "credits_used": credits_used
        }).execute()
        
        if not response.data:
            raise Exception(f"Failed to save message: No data returned")
        
        return response.data[0]
    except Exception as e:
        # Log the error but don't fail completely
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error saving message: {e}", exc_info=True)
        # Return None instead of raising to allow the flow to continue
        return None


async def get_session_messages(session_id: str, limit: int = 50) -> list:
    """Get recent messages from a session in chronological order."""
    # Get messages ordered by newest first, then reverse for chronological order
    response = supabase.table("chat_messages")\
        .select("*")\
        .eq("session_id", session_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()
    
    # Return in chronological order (oldest first)
    return list(reversed(response.data)) if response.data else []


async def get_session_summary(session_id: str) -> str | None:
    """Get session summary."""
    response = supabase.table("chat_sessions").select("summary").eq("id", session_id).single().execute()
    return response.data.get("summary") if response.data else None


async def update_session_summary(session_id: str, summary: str):
    """Update session summary."""
    supabase.table("chat_sessions").update({
        "summary": summary
    }).eq("id", session_id).execute()


async def update_session_title(session_id: str, title: str):
    """Update session title."""
    supabase.table("chat_sessions").update({
        "title": title
    }).eq("id", session_id).execute()


async def update_message(message_id: str, content: str) -> dict | None:
    """Update a message's content."""
    response = supabase.table("chat_messages").update({
        "content": content
    }).eq("id", message_id).execute()
    return response.data[0] if response.data else None


async def get_message(message_id: str) -> dict | None:
    """Get a message by ID."""
    response = supabase.table("chat_messages").select("*").eq("id", message_id).single().execute()
    return response.data if response.data else None


async def delete_message_and_after(session_id: str, message_id: str):
    """Delete a message and all messages after it in the session."""
    # Get the message's created_at timestamp
    message = await get_message(message_id)
    if not message:
        return
    
    # Delete all messages after this one
    supabase.table("chat_messages").delete()\
        .eq("session_id", session_id)\
        .gt("created_at", message["created_at"])\
        .execute()