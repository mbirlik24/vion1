from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from typing import Literal
# Rate limiting temporarily disabled - will be re-enabled with proper implementation
# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.util import get_remote_address
# from slowapi.errors import RateLimitExceeded
import json
import logging
import asyncio

from app.services.auth import get_current_user
from app.services.rate_limiter import (
    check_rate_limit,
    acquire_request_slot,
    release_request_slot,
    get_user_request_stats,
)
from app.services.error_messages import (
    INSUFFICIENT_CREDITS,
    IMAGE_GENERATION_ERROR,
    INTERNAL_SERVER_ERROR,
    UNAUTHORIZED,
    NOT_FOUND,
    format_error,
    ErrorCodes,
)

logger = logging.getLogger(__name__)
from app.services.supabase_client import (
    get_user_credits,
    deduct_credits,
    save_message,
    get_session_messages,
    get_session_summary,
    update_session_summary,
    update_session_title,
    update_message,
    delete_message_and_after,
    get_message,
)
from app.services.smart_router import (
    get_model_for_message,
    generate_response_stream,
    generate_summary,
    generate_title,
    get_system_prompt,
)
from app.config import get_settings
from openai import RateLimitError, APIError

router = APIRouter()
settings = get_settings()

# Rate limiting temporarily simplified - will be properly implemented later


class ChatRequest(BaseModel):
    message: str
    session_id: str
    mode: Literal["auto", "fast", "pro"] = "auto"


class ChatResponse(BaseModel):
    message: str
    model_used: str
    credits_used: float


@router.post("")
async def chat(
    http_request: Request,
    chat_request: ChatRequest,
    user: dict = Depends(get_current_user)
):
    """
    Main chat endpoint with smart model routing and streaming response.
    Rate limited to 30 requests per minute per user.
    """
    try:
        user_id = user["id"]
        # Store user_id in request state for rate limiting
        http_request.state.user_id = user_id
        
        # Log incoming request
        logger.info("=" * 80)
        logger.info(f"📥 YENİ İSTEK GELDİ")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Session ID: {chat_request.session_id}")
        logger.info(f"   Mode: {chat_request.mode}")
        logger.info(f"   Message: {chat_request.message[:100]}{'...' if len(chat_request.message) > 100 else ''}")
        logger.info(f"   Message Length: {len(chat_request.message)} karakter")
        
        # Check rate limit
        allowed, error_msg = await check_rate_limit(user_id)
        if not allowed:
            logger.warning(f"❌ Rate limit aşıldı - User: {user_id}")
            raise HTTPException(
                status_code=429,
                detail=error_msg,
                headers={"X-Error-Code": ErrorCodes.RATE_LIMIT_EXCEEDED}
            )
        logger.info(f"✅ Rate limit kontrolü geçti - User: {user_id}")
        
        # Acquire concurrent request slot
        slot_acquired, slot_error_msg = await acquire_request_slot(user_id)
        if not slot_acquired:
            logger.warning(f"❌ Eşzamanlı istek limiti aşıldı - User: {user_id}")
            raise HTTPException(
                status_code=429,
                detail=slot_error_msg,
                headers={"X-Error-Code": ErrorCodes.CONCURRENT_REQUESTS_EXCEEDED}
            )
        logger.info(f"✅ Eşzamanlı istek slotu alındı - User: {user_id}")
        
        # PARALLEL OPTIMIZATION: Start multiple operations in parallel for faster response
        # This reduces total wait time by running independent operations concurrently
        # Start parallel operations
        credits_task = asyncio.create_task(get_user_credits(user_id))
        model_task = asyncio.create_task(get_model_for_message(chat_request.message, chat_request.mode))
        context_task = asyncio.create_task(get_session_messages(chat_request.session_id, limit=50))
        summary_task = asyncio.create_task(get_session_summary(chat_request.session_id))
        
        # Wait for all parallel operations
        credits, (model, cost, route), previous_messages, summary = await asyncio.gather(
            credits_task, model_task, context_task, summary_task
        )
        
        # Log model selection and routing decision
        logger.info("=" * 80)
        logger.info(f"🎯 MODEL SEÇİMİ VE YÖNLENDİRME KARARI")
        logger.info(f"   Seçilen Model: {model}")
        logger.info(f"   Model Maliyeti: {cost} kredi")
        logger.info(f"   Yönlendirme Route: {route}")
        logger.info(f"   Kullanıcı Kredisi: {credits} kredi")
        logger.info(f"   Önceki Mesaj Sayısı: {len(previous_messages)}")
        logger.info(f"   Özet Mevcut: {'Evet' if summary else 'Hayır'}")
        logger.info("=" * 80)
        
        # Check if user has enough credits
        if credits < cost:
            error_msg = format_error(
                INSUFFICIENT_CREDITS,
                required=cost,
                available=credits
            )
            raise HTTPException(
                status_code=402,
                detail=error_msg,
                headers={"X-Error-Code": ErrorCodes.INSUFFICIENT_CREDITS}
            )
        
        # Handle image generation requests
        if model == "image":
            logger.info("🖼️  GÖRSEL ÜRETİM İSTEĞİ TESPİT EDİLDİ")
            # Extract prompt from message (remove image generation keywords)
            prompt = chat_request.message.strip()
            
            # Clean up common prefixes (Turkish and English)
            prefixes_to_remove = [
                "generate image of", "create image of", "draw", "generate an image of",
                "create an image of", "make an image of", "show me an image of",
                "resim oluştur", "görsel oluştur", "resim çiz", "görsel üret",
                "resim yap", "görsel yap", "bir resim", "bir görsel",
                "generate image", "create image", "generate an image", "create an image",
                "resim", "görsel", "image generate", "image create"
            ]
            
            prompt_lower = prompt.lower()
            for prefix in prefixes_to_remove:
                if prompt_lower.startswith(prefix):
                    prompt = prompt[len(prefix):].strip()
                    # Remove common connecting words
                    for connector in ["of", ":", "-", "için", "bir"]:
                        if prompt.lower().startswith(connector + " "):
                            prompt = prompt[len(connector) + 1:].strip()
                    break
            
            # If prompt is empty or too short, use original message
            if not prompt or len(prompt) < 3:
                prompt = chat_request.message.strip()
            
            # Generate image
            from openai import AsyncOpenAI
            from app.config import get_settings
            settings = get_settings()
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            
            try:
                # Save user message
                await save_message(
                    session_id=chat_request.session_id,
                    role="user",
                    content=chat_request.message
                )
                
                # Send loading message
                async def generate():
                    try:
                        # Send initial status
                        yield f"data: {json.dumps({'type': 'status', 'content': '🎨 Görsel oluşturuluyor, lütfen bekleyin...', 'model': 'dall-e-3', 'route': route})}\n\n"
                        
                        # Generate image
                        response = await client.images.generate(
                            model="dall-e-3",
                            prompt=prompt,
                            size="1024x1024",
                            quality="standard",
                            n=1,
                        )
                        
                        if not response.data or len(response.data) == 0:
                            raise Exception("No image data received from OpenAI")
                        
                        image_url = response.data[0].url
                        
                        if not image_url:
                            raise Exception("Image URL is empty")
                        
                        logger.info(f"Generated image URL: {image_url}")
                        
                        # Save assistant message with image
                        image_content = f"![Generated Image]({image_url})\n\n**Prompt:** {prompt}"
                        try:
                            await save_message(
                                session_id=chat_request.session_id,
                                role="assistant",
                                content=image_content,
                                model_used="dall-e-3",
                                credits_used=cost
                            )
                        except Exception as save_error:
                            logger.error(f"Error saving image message: {save_error}", exc_info=True)
                            # Continue even if save fails - we still want to send the image
                        
                        # Deduct credits
                        deducted = await deduct_credits(
                            user_id=user_id,
                            amount=cost,
                            description="Image generation with DALL-E 3"
                        )
                        if not deducted:
                            logger.warning(f"Failed to deduct credits for user {user_id}, but image was generated")
                        
                        # Send image data - make sure all required fields are present
                        image_response = {
                            'type': 'image',
                            'image_url': image_url,
                            'prompt': prompt,
                            'model': 'dall-e-3',
                            'route': route
                        }
                        yield f"data: {json.dumps(image_response)}\n\n"
                        yield f"data: [DONE]\n\n"
                    except Exception as e:
                        logger.error(f"Error generating image: {e}", exc_info=True)
                        error_msg = format_error(IMAGE_GENERATION_ERROR)
                        yield f"data: {json.dumps({'type': 'error', 'error': error_msg, 'code': ErrorCodes.IMAGE_GENERATION_ERROR})}\n\n"
                        raise
                
                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Model-Used": "dall-e-3",
                        "X-Credits-Used": str(cost),
                        "X-Route-Mode": route,
                    }
                )
            except Exception as e:
                logger.error(f"Error in image generation: {e}", exc_info=True)
                error_msg = format_error(IMAGE_GENERATION_ERROR)
                raise HTTPException(
                    status_code=500,
                    detail=error_msg,
                    headers={"X-Error-Code": ErrorCodes.IMAGE_GENERATION_ERROR}
                )
        
        # Normal chat flow
        logger.info("💬 NORMAL CHAT AKIŞI BAŞLADI")
        # Save user message (non-blocking, can happen in parallel)
        save_message_task = asyncio.create_task(
            save_message(
                session_id=chat_request.session_id,
                role="user",
                content=chat_request.message
            )
        )
        
        # Build context messages (already have previous_messages and summary from parallel fetch)
        context_messages = []
        
        # Add summary as context if available
        if summary:
            context_messages.append({
                "role": "system",
                "content": f"Previous conversation summary: {summary}"
            })
            logger.info(f"📝 Özet context'e eklendi: {summary[:50]}...")
        
        # Add previous messages
        for msg in previous_messages:
            context_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current message
        context_messages.append({
            "role": "user",
            "content": chat_request.message
        })
        
        logger.info(f"📋 Toplam context mesaj sayısı: {len(context_messages)}")
        
        # Generate title for new sessions (if first message) - in background, don't wait
        if len(previous_messages) <= 1:
            logger.info("📌 Yeni session - başlık oluşturulacak (arka planda)")
            async def generate_title_background():
                try:
                    title = await generate_title(chat_request.message)
                    await update_session_title(chat_request.session_id, title)
                    logger.info(f"✅ Session başlığı oluşturuldu: {title}")
                except Exception as e:
                    logger.warning(f"❌ Başlık oluşturma hatası: {e}")
            # Don't await - let it run in background
            asyncio.create_task(generate_title_background())
        
        # Generate optimal system prompt based on user's language (synchronous, fast)
        system_prompt = get_system_prompt(chat_request.message, context_messages)
        logger.info(f"🤖 System prompt oluşturuldu (uzunluk: {len(system_prompt)} karakter)")
        
        async def generate():
            full_response = ""
            
            try:
                logger.info("🚀 OpenAI API çağrısı başlatılıyor...")
                logger.info(f"   Model: {model}")
                logger.info(f"   System Prompt: {system_prompt[:100]}...")
                logger.info(f"   Context Mesajları: {len(context_messages)}")
                
                # Use character-by-character streaming for smooth ChatGPT-like experience
                chunk_count = 0
                async for chunk in generate_response_stream(
                    messages=context_messages,
                    model=model,
                    system_prompt=system_prompt,
                    character_streaming=True  # Enable smooth character-by-character streaming
                ):
                    full_response += chunk
                    chunk_count += 1
                    # Send chunk as SSE
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk, 'model': model, 'route': route})}\n\n"
                
                logger.info(f"✅ Yanıt alındı - Toplam chunk: {chunk_count}, Toplam karakter: {len(full_response)}")
                
                # Deduct credits after successful response
                logger.info(f"💳 Kredi düşülüyor: {cost} kredi")
                deducted = await deduct_credits(
                    user_id=user_id,
                    amount=cost,
                    description=f"Chat with {model}"
                )
                if not deducted:
                    logger.error(f"❌ Kredi düşürme başarısız - User: {user_id}")
                    raise Exception("Failed to deduct credits")
                logger.info(f"✅ Kredi başarıyla düşürüldü")
                
                # Save assistant message
                logger.info("💾 Assistant mesajı kaydediliyor...")
                await save_message(
                    session_id=chat_request.session_id,
                    role="assistant",
                    content=full_response,
                    model_used=model,
                    credits_used=cost
                )
                logger.info("✅ Assistant mesajı kaydedildi")
                
                # Check if we need to update summary (every 20 messages for better performance)
                all_messages = await get_session_messages(chat_request.session_id, limit=100)
                if len(all_messages) % 20 == 0 and len(all_messages) > 0:
                    try:
                        new_summary = await generate_summary([
                            {"role": m["role"], "content": m["content"]}
                            for m in all_messages[-10:]
                        ])
                        if new_summary:
                            await update_session_summary(chat_request.session_id, new_summary)
                    except Exception as e:
                        logger.warning(f"Failed to generate summary: {e}")
                
                # Send completion signal
                yield f"data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error in streaming response: {e}", exc_info=True)
                # Send user-friendly error as SSE before closing
                if isinstance(e, (RateLimitError, APIError)):
                    from app.services.error_messages import OPENAI_RATE_LIMIT, OPENAI_API_ERROR, ErrorCodes
                    if isinstance(e, RateLimitError):
                        error_msg = format_error(OPENAI_RATE_LIMIT)
                        error_code = ErrorCodes.OPENAI_RATE_LIMIT
                    else:
                        error_msg = format_error(OPENAI_API_ERROR)
                        error_code = ErrorCodes.OPENAI_API_ERROR
                else:
                    error_msg = format_error(INTERNAL_SERVER_ERROR)
                    error_code = ErrorCodes.INTERNAL_SERVER_ERROR
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg, 'code': error_code})}\n\n"
                raise
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Model-Used": model,
                "X-Credits-Used": str(cost),
                "X-Route-Mode": route,
            }
        )
    except HTTPException:
        # Re-raise HTTP exceptions (they're already properly formatted)
        raise
    except Exception as e:
        # Log the full error for debugging
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        # Catch any other exceptions and return user-friendly error
        error_msg = format_error(INTERNAL_SERVER_ERROR)
        raise HTTPException(
            status_code=500,
            detail=error_msg,
            headers={"X-Error-Code": ErrorCodes.INTERNAL_SERVER_ERROR}
        )
    finally:
        # Always release the request slot
        logger.info("=" * 80)
        logger.info(f"🏁 İSTEK TAMAMLANDI - User: {user_id}, Session: {chat_request.session_id}")
        logger.info("=" * 80)
        await release_request_slot(user_id)


@router.get("/history/{session_id}")
async def get_chat_history(
    http_request: Request,
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """Get chat history for a session."""
    messages = await get_session_messages(session_id, limit=100)
    return {"messages": messages}


class EditMessageRequest(BaseModel):
    message_id: str
    new_content: str
    session_id: str


@router.post("/edit")
async def edit_message(
    http_request: Request,
    request: EditMessageRequest,
    user: dict = Depends(get_current_user)
):
    """Edit a message and regenerate response from that point."""
    try:
        user_id = user["id"]
        
        # Verify message belongs to user's session
        message = await get_message(request.message_id)
        if not message:
            error_msg = format_error(NOT_FOUND)
            raise HTTPException(
                status_code=404,
                detail=error_msg,
                headers={"X-Error-Code": ErrorCodes.NOT_FOUND}
            )
        
        # Get session to verify ownership
        from app.services.supabase_client import supabase
        session_response = supabase.table("chat_sessions")\
            .select("user_id")\
            .eq("id", request.session_id)\
            .single()\
            .execute()
        
        if not session_response.data or session_response.data["user_id"] != user_id:
            error_msg = format_error(UNAUTHORIZED)
            raise HTTPException(
                status_code=403,
                detail=error_msg,
                headers={"X-Error-Code": ErrorCodes.UNAUTHORIZED}
            )
        
        # Update the message
        await update_message(request.message_id, request.new_content)
        
        # Delete all messages after this one
        await delete_message_and_after(request.session_id, request.message_id)
        
        # Get context up to this message
        all_messages = await get_session_messages(request.session_id, limit=100)
        message_index = next((i for i, m in enumerate(all_messages) if m["id"] == request.message_id), -1)
        
        if message_index == -1:
            from app.services.error_messages import MESSAGE_NOT_FOUND
            error_msg = format_error(MESSAGE_NOT_FOUND)
            raise HTTPException(
                status_code=404,
                detail=error_msg,
                headers={"X-Error-Code": ErrorCodes.NOT_FOUND}
            )
        
        # Get messages up to and including the edited message
        context_messages = all_messages[:message_index + 1]
        
        # PARALLEL OPTIMIZATION: Get model and credits in parallel
        model_task = asyncio.create_task(get_model_for_message(request.new_content, "auto"))
        credits_task = asyncio.create_task(get_user_credits(user_id))
        summary_task = asyncio.create_task(get_session_summary(request.session_id))
        
        # Wait for parallel operations
        (model, cost, route), credits, summary = await asyncio.gather(
            model_task, credits_task, summary_task
        )
        
        if credits < cost:
            error_msg = format_error(
                INSUFFICIENT_CREDITS,
                required=cost,
                available=credits
            )
            raise HTTPException(
                status_code=402,
                detail=error_msg,
                headers={"X-Error-Code": ErrorCodes.INSUFFICIENT_CREDITS}
            )
        
        # Build context with summary (already fetched in parallel)
        formatted_messages = []
        if summary:
            formatted_messages.append({
                "role": "system",
                "content": f"Previous conversation summary: {summary}"
            })
        
        for msg in context_messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Generate optimal system prompt based on user's language (synchronous, fast)
        system_prompt = get_system_prompt(request.new_content, formatted_messages)
        
        # Generate new response
        async def generate():
            full_response = ""
            try:
                # Use character-by-character streaming for smooth ChatGPT-like experience
                async for chunk in generate_response_stream(
                    messages=formatted_messages,
                    model=model,
                    system_prompt=system_prompt,
                    character_streaming=True  # Enable smooth character-by-character streaming
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk, 'model': model, 'route': route})}\n\n"
                
                # Deduct credits
                deducted = await deduct_credits(
                    user_id=user_id,
                    amount=cost,
                    description=f"Chat with {model} (edited)"
                )
                if not deducted:
                    raise Exception("Failed to deduct credits")
                
                # Save assistant message
                await save_message(
                    session_id=request.session_id,
                    role="assistant",
                    content=full_response,
                    model_used=model,
                    credits_used=cost
                )
                
                yield f"data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Error in edit streaming response: {e}", exc_info=True)
                error_msg = format_error(INTERNAL_SERVER_ERROR)
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg, 'code': ErrorCodes.INTERNAL_SERVER_ERROR})}\n\n"
                raise
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Model-Used": model,
                "X-Credits-Used": str(cost),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in edit endpoint: {e}", exc_info=True)
        error_msg = format_error(INTERNAL_SERVER_ERROR)
        raise HTTPException(
            status_code=500,
            detail=error_msg,
            headers={"X-Error-Code": ErrorCodes.INTERNAL_SERVER_ERROR}
        )


class GenerateImageRequest(BaseModel):
    prompt: str
    session_id: str
    size: Literal["256x256", "512x512", "1024x1024"] = "1024x1024"


@router.post("/generate-image")
async def generate_image(
    http_request: Request,
    request: GenerateImageRequest,
    user: dict = Depends(get_current_user)
):
    """Generate an image using DALL-E."""
    try:
        user_id = user["id"]
        
        # Image generation costs (adjust based on your pricing)
        image_cost = 10.0  # 10 credits per image
        
        # Check credits
        credits = await get_user_credits(user_id)
        if credits < image_cost:
            error_msg = format_error(
                INSUFFICIENT_CREDITS,
                required=image_cost,
                available=credits
            )
            raise HTTPException(
                status_code=402,
                detail=error_msg,
                headers={"X-Error-Code": ErrorCodes.INSUFFICIENT_CREDITS}
            )
        
        # Generate image using OpenAI
        from openai import AsyncOpenAI
        from app.config import get_settings
        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        response = await client.images.generate(
            model="dall-e-3",
            prompt=request.prompt,
            size=request.size,
            quality="standard",
            n=1,
        )
        
        image_url = response.data[0].url
        
        # Save user message with image prompt
        await save_message(
            session_id=request.session_id,
            role="user",
            content=f"[Image Request] {request.prompt}"
        )
        
        # Save assistant message with image
        await save_message(
            session_id=request.session_id,
            role="assistant",
            content=f"![Generated Image]({image_url})\n\n**Prompt:** {request.prompt}",
            model_used="dall-e-3",
            credits_used=image_cost
        )
        
        # Deduct credits
        deducted = await deduct_credits(
            user_id=user_id,
            amount=image_cost,
            description="Image generation with DALL-E 3"
        )
        if not deducted:
            raise Exception("Failed to deduct credits")
        
        return {
            "image_url": image_url,
            "prompt": request.prompt,
            "credits_used": image_cost
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating image: {e}", exc_info=True)
        error_msg = format_error(IMAGE_GENERATION_ERROR)
        raise HTTPException(
            status_code=500,
            detail=error_msg,
            headers={"X-Error-Code": ErrorCodes.IMAGE_GENERATION_ERROR}
        )
