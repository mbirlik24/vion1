from openai import AsyncOpenAI
from app.config import get_settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import APIError, RateLimitError, APITimeoutError
from app.services.api_key_manager import get_openai_client_with_rotation, handle_openai_error
from app.services.error_messages import (
    OPENAI_RATE_LIMIT,
    OPENAI_API_ERROR,
    OPENAI_TIMEOUT,
    MODEL_NOT_AVAILABLE,
    format_error,
)
import re
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

# Use primary client for now, rotation will be used in retry logic
_primary_client = AsyncOpenAI(api_key=settings.openai_api_key)

# Classification prompt for routing
CLASSIFICATION_PROMPT = """You are a message classifier. Analyze the user's message and classify it as either SIMPLE or COMPLEX.

SIMPLE messages include:
- Greetings and casual conversation (merhaba, selam, nasılsın, hello, hi)
- Basic factual questions (what is X, X nedir, simple definitions)
- Simple summaries or explanations
- Quick translations
- Basic formatting tasks
- Simple yes/no questions
- Basic information requests
- Short, straightforward questions that can be answered in 1-2 sentences

COMPLEX messages include:
- Coding tasks (writing, debugging, reviewing code, kod yaz, program, algoritma)
- Mathematical problems and calculations (hesapla, çöz, problem, equation)
- Advanced reasoning or logic puzzles
- Creative writing (stories, poems, essays, hikaye, şiir, yazı)
- Data analysis (veri analizi, data analysis)
- Multi-step instructions (adım adım, step by step)
- Technical explanations requiring deep understanding (teknik açıklama, how does X work in detail)
- Scientific or academic questions (biology, physics, chemistry, engineering concepts)
- Questions about complex systems, mechanisms, or processes (how and why questions)
- Research tasks (araştır, research)
- Complex problem solving
- Code review or debugging requests
- Questions requiring step-by-step reasoning or multiple concepts
- Tasks that need creative thinking or generation of new content
- Long messages (>150 characters) that require detailed explanations
- Questions with multiple parts or sub-questions
- Questions about theoretical concepts, models, or frameworks
- Questions asking "how and why" or "nasıl ve neden" (both mechanism and reason)

IMPORTANT: 
- If a question could be answered simply but might benefit from deeper explanation, classify as COMPLEX
- When in doubt between SIMPLE and COMPLEX, ALWAYS choose COMPLEX to ensure quality
- Technical "what is X" questions are SIMPLE, but "how does X work" or "explain X in detail" are COMPLEX
- Scientific, biological, or academic questions are almost always COMPLEX
- Questions asking for both "how" and "why" are COMPLEX
- Long messages (>150 chars) are typically COMPLEX unless clearly a simple greeting

Respond with ONLY the word "SIMPLE" or "COMPLEX" - nothing else, no punctuation, no explanation.
"""


def _parse_classification(response_text: str) -> str | None:
    """
    Parse classification from model response.
    Handles cases like "SIMPLE.", "COMPLEX message", "The answer is SIMPLE", etc.
    Returns "SIMPLE", "COMPLEX", or None if unclear.
    """
    if not response_text:
        return None
    
    text = response_text.strip().upper()
    
    # Direct match
    if text == "SIMPLE" or text == "COMPLEX":
        return text
    
    # Check if SIMPLE or COMPLEX appears in the text
    if "COMPLEX" in text:
        return "COMPLEX"
    if "SIMPLE" in text:
        return "SIMPLE"
    
    return None


def _fast_classify_heuristic(message: str) -> str | None:
    """
    Fast heuristic classification using pattern matching and complexity analysis.
    Returns "SIMPLE", "COMPLEX", or None if uncertain (needs AI classification).
    This is much faster than AI classification and catches most obvious cases.
    
    Strategy: When in doubt, prefer COMPLEX to ensure quality responses.
    """
    message_lower = message.lower().strip()
    message_length = len(message)
    
    # COMPLEXITY INDICATORS - If any of these are present, classify as COMPLEX
    
    # 1. Long messages (typically require detailed explanations)
    if message_length > 200:
        logger.debug(f"Message classified as COMPLEX due to length ({message_length} chars)")
        return "COMPLEX"
    
    # 2. Multiple sentences with question marks (deep questions)
    question_count = message.count("?") + message.count("?")
    if question_count >= 2 and message_length > 100:
        logger.debug(f"Message classified as COMPLEX due to multiple questions ({question_count})")
        return "COMPLEX"
    
    # 3. Technical/scientific terms (academic complexity)
    technical_terms = [
        # Scientific/biological terms
        "hücre", "cell", "biyolojik", "biological", "ökaryotik", "eukaryotic",
        "viskoelastik", "viscoelastic", "deformasyon", "deformation", "mekanik", "mechanical",
        "fizik", "physics", "kimya", "chemistry", "matematik", "mathematics",
        # Technical terms
        "kod", "code", "program", "algoritma", "algorithm", "debug", "function", "fonksiyon",
        "class", "api", "database", "server", "framework", "library", "kütüphane",
        "hesapla", "calculate", "çöz", "solve", "problem", "equation", "formül", "formula",
        "teknik", "technical", "mühendislik", "engineering", "sistem", "system",
        # Deep explanation requests
        "nasıl çalışır", "how does", "how it works", "neden", "why", "açıkla", "explain",
        "detaylı", "detailed", "derinlemesine", "in depth", "adım adım", "step by step",
        # Academic/research terms
        "araştır", "research", "analiz", "analysis", "veri", "data", "model", "modelleme",
        "teori", "theory", "kavram", "concept", "prensipler", "principles"
    ]
    
    technical_term_count = sum(1 for term in technical_terms if term in message_lower)
    if technical_term_count >= 3:
        logger.debug(f"Message classified as COMPLEX due to technical terms ({technical_term_count})")
        return "COMPLEX"
    
    # 4. Obvious COMPLEX patterns (high confidence)
    complex_patterns = [
        "kod", "code", "program", "algoritma", "algorithm", "debug", "function", "fonksiyon",
        "class", "api", "database", "server", "framework", "library", "kütüphane",
        "hesapla", "calculate", "çöz", "solve", "problem", "equation", "formül",
        "yaz", "write", "şiir", "poem", "hikaye", "story", "öykü", "yarat", "create",
        "araştır", "research", "analiz", "analysis", "veri", "data",
        "adım adım", "step by step", "nasıl çalışır", "how does", "explain in detail",
        "teknik", "technical", "detaylı", "detailed", "açıkla", "explain",
        # Deep question patterns
        "nasıl ve neden", "how and why", "neden ve nasıl", "why and how",
        "derinlemesine", "in depth", "detaylı açıkla", "explain in detail"
    ]
    
    # Check for complex patterns first (they take priority)
    for pattern in complex_patterns:
        if pattern in message_lower:
            # Additional check: if it's a very short message with just a greeting, it might be simple
            if message_length < 20 and any(greeting in message_lower for greeting in ["merhaba", "hello", "hi", "selam"]):
                continue
            logger.debug(f"Message classified as COMPLEX due to pattern: '{pattern}'")
            return "COMPLEX"
    
    # 5. Medium-length messages with "how/why" questions are likely complex
    if message_length > 80 and message_length <= 200:
        deep_question_words = ["nasıl", "how", "neden", "why", "niçin", "açıkla", "explain", "detaylı", "detailed"]
        if any(word in message_lower for word in deep_question_words) and question_count >= 1:
            logger.debug(f"Message classified as COMPLEX due to deep question in medium-length message")
            return "COMPLEX"
    
    # SIMPLE INDICATORS - Only classify as SIMPLE if message is clearly simple
    
    # Obvious SIMPLE patterns (high confidence, but only for short messages)
    simple_patterns = [
        "merhaba", "hello", "hi", "selam", "nasılsın", "how are", "teşekkür", "thanks",
        "nedir", "what is", "ne demek", "what does", "basit", "simple", "kısa", "short"
    ]
    
    # Check for simple patterns (only if message is short and simple)
    if message_length < 50:
        for pattern in simple_patterns:
            if pattern in message_lower:
                # Make sure it's not mixed with complex patterns
                if not any(cp in message_lower for cp in complex_patterns):
                    logger.debug(f"Message classified as SIMPLE due to pattern: '{pattern}'")
                    return "SIMPLE"
    
    # If uncertain, return None to use AI classification
    # But for longer messages (>150 chars), default to COMPLEX to ensure quality
    if message_length > 150:
        logger.debug(f"Uncertain classification for long message ({message_length} chars), defaulting to COMPLEX")
        return "COMPLEX"
    
    return None


async def classify_message(message: str) -> tuple[str, str | None]:
    """
    Classify a message as SIMPLE or COMPLEX using fast heuristic first, then AI if needed.
    Returns: ("SIMPLE" | "COMPLEX", error_reason | None)
    """
    logger.info("🔍 MESAJ SINIFLANDIRMA BAŞLADI")
    logger.info(f"   Mesaj: {message[:100]}{'...' if len(message) > 100 else ''}")
    
    # Try fast heuristic classification first (much faster)
    heuristic_result = _fast_classify_heuristic(message)
    if heuristic_result:
        logger.info(f"✅ Heuristic sınıflandırma sonucu: {heuristic_result}")
        logger.info(f"   (AI sınıflandırmaya gerek yok - hızlı heuristic yeterli)")
        return heuristic_result, None
    
    # If heuristic is uncertain, use AI classification
    logger.info("🤖 Heuristic belirsiz - AI sınıflandırması kullanılıyor...")
    client = _primary_client
    key_used = None
    
    try:
        logger.info(f"   Classification model: {settings.simple_model}")
        # Use faster model settings for classification
        response = await client.chat.completions.create(
            model=settings.simple_model,
            messages=[
                {"role": "system", "content": CLASSIFICATION_PROMPT},
                {"role": "user", "content": message}
            ],
            max_tokens=10,
            temperature=0,
            # Reduce timeout for faster failure
            timeout=5.0,
        )
        
        raw_response = response.choices[0].message.content
        logger.info(f"   AI ham yanıtı: '{raw_response}'")
        classification = _parse_classification(raw_response)
        
        if classification is None:
            # Log the unexpected response for debugging
            logger.warning(f"⚠️  Beklenmeyen sınıflandırma yanıtı: '{raw_response}' - SIMPLE'a varsayılan")
            # Default to SIMPLE if classification is unclear (cost-saving strategy)
            return "SIMPLE", "invalid_classification"
        
        logger.info(f"✅ AI sınıflandırma sonucu: {classification}")
        return classification, None
    
    except (RateLimitError, APIError) as e:
        logger.warning(f"⚠️  Classification rate limit/error: {e}")
        logger.info("🔄 API key rotation deneniyor...")
        # Try with key rotation
        try:
            client, key_used = await get_openai_client_with_rotation()
            logger.info(f"✅ Yeni API key ile tekrar deneniyor (key: {key_used[:10]}...{key_used[-4:] if key_used else 'N/A'})")
            response = await client.chat.completions.create(
                model=settings.simple_model,
                messages=[
                    {"role": "system", "content": CLASSIFICATION_PROMPT},
                    {"role": "user", "content": message}
                ],
                max_tokens=10,
                temperature=0,
                timeout=5.0,
            )
            
            raw_response = response.choices[0].message.content
            logger.info(f"   Retry AI ham yanıtı: '{raw_response}'")
            classification = _parse_classification(raw_response)
            
            if classification is None:
                logger.warning(f"⚠️  Retry sonrası beklenmeyen yanıt: '{raw_response}' - SIMPLE'a varsayılan")
                return "SIMPLE", "invalid_classification"
            
            logger.info(f"✅ Retry sonrası AI sınıflandırma: {classification}")
            return classification, None
        except Exception as retry_error:
            if key_used:
                await handle_openai_error(retry_error, key_used)
            logger.error(f"❌ Retry sonrası classification hatası: {retry_error}", exc_info=True)
            return "SIMPLE", "classification_error"
    
    except Exception as e:
        logger.error(f"❌ Classification hatası: {e}", exc_info=True)
        # Default to SIMPLE on error to save costs
        return "SIMPLE", "classification_error"


def is_image_generation_request(message: str) -> bool:
    """
    Detect if the message is requesting image generation.
    Checks for common patterns like "generate image", "create image", "draw", "resim", etc.
    """
    message_lower = message.lower().strip()
    
    # Turkish and English keywords for image generation
    image_keywords = [
        "generate image", "create image", "draw", "resim", "görsel", "görsel oluştur",
        "resim oluştur", "resim çiz", "görsel üret", "image generate", "image create",
        "make an image", "show me an image", "bana bir resim", "bir görsel",
        "dall-e", "dalle", "görsel yap", "resim yap"
    ]
    
    # Check if message contains image generation keywords
    for keyword in image_keywords:
        if keyword in message_lower:
            return True
    
    # Check if message starts with image generation commands
    if message_lower.startswith(("generate", "create", "draw", "resim", "görsel")):
        return True
    
    return False


async def get_model_for_message(message: str, mode: str = "auto") -> tuple[str, float, str]:
    """
    Determine which model to use based on message classification and mode.
    
    Args:
        message: The user's message
        mode: "auto" (smart routing), "fast" (always simple), or "pro" (always complex)
    
    Returns:
        Tuple of (model_name, credit_cost, route)
    """
    logger.info("=" * 80)
    logger.info(f"🎯 MODEL SEÇİMİ FONKSİYONU ÇAĞRILDI")
    logger.info(f"   Mode: {mode}")
    logger.info(f"   Mesaj: {message[:100]}{'...' if len(message) > 100 else ''}")
    
    # Check for image generation request first
    if is_image_generation_request(message):
        logger.info("🖼️  Görsel üretim isteği tespit edildi - DALL-E 3'e yönlendiriliyor")
        return "image", 10.0, "image"
    
    # Fast mode: always use the cheaper/smaller model (maximum speed)
    if mode == "fast":
        logger.info(f"⚡ Fast mode - {settings.simple_model} kullanılacak")
        logger.info(f"   Model: {settings.simple_model}")
        logger.info(f"   Maliyet: {settings.simple_model_cost} kredi")
        return settings.simple_model, settings.simple_model_cost, "fast"
    
    # Pro mode: always use the stronger model (slower, more capable)
    if mode == "pro":
        logger.info(f"🚀 Pro mode - {settings.complex_model} kullanılacak")
        logger.info(f"   Model: {settings.complex_model}")
        logger.info(f"   Maliyet: {settings.complex_model_cost} kredi")
        return settings.complex_model, settings.complex_model_cost, "pro"
    
    # Auto mode: use GPT-4o-mini to quickly classify the message, then route accordingly
    logger.info("🤖 Auto mode - Mesaj sınıflandırılıyor...")
    classification, error = await classify_message(message)
    
    if classification == "COMPLEX":
        logger.info(f"📊 Sınıflandırma: COMPLEX - {settings.complex_model} kullanılacak")
        logger.info(f"   Model: {settings.complex_model}")
        logger.info(f"   Maliyet: {settings.complex_model_cost} kredi")
        logger.info(f"   Route: auto:complex{':error' if error else ''}")
        return settings.complex_model, settings.complex_model_cost, f"auto:complex{':error' if error else ''}"
    else:
        # Default to SIMPLE (including on error to save costs)
        logger.info(f"📊 Sınıflandırma: SIMPLE - {settings.simple_model} kullanılacak")
        logger.info(f"   Model: {settings.simple_model}")
        logger.info(f"   Maliyet: {settings.simple_model_cost} kredi")
        logger.info(f"   Route: auto:simple{':error' if error else ''}")
        if error:
            logger.warning(f"   ⚠️  Sınıflandırma hatası: {error}")
        return settings.simple_model, settings.simple_model_cost, f"auto:simple{':error' if error else ''}"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
    reraise=True
)
async def _create_chat_completion_with_retry(model: str, messages: list[dict]):
    """Create chat completion with retry logic and API key rotation."""
    logger.info(f"🔄 Chat completion oluşturuluyor - Model: {model}")
    client = _primary_client
    key_used = None
    
    try:
        logger.info(f"   İlk deneme - Primary client kullanılıyor")
        return await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=4096,
        )
    except (RateLimitError, APIError) as e:
        # Try with different API key on rate limit
        logger.warning(f"⚠️  Rate limit/API error: {e}")
        logger.info("🔄 API key rotation deneniyor...")
        try:
            client, key_used = await get_openai_client_with_rotation()
            logger.info(f"✅ Yeni API key ile tekrar deneniyor (key: {key_used[:10]}...{key_used[-4:] if key_used else 'N/A'})")
            return await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=4096,
            )
        except Exception as retry_error:
            if key_used:
                await handle_openai_error(retry_error, key_used)
            logger.error(f"❌ Retry sonrası hata: {retry_error}", exc_info=True)
            raise retry_error
    except Exception as e:
        logger.error(f"❌ Chat completion hatası: {e}", exc_info=True)
        raise


async def generate_response_stream(
    messages: list[dict],
    model: str,
    system_prompt: str = None,
    character_streaming: bool = True
):
    """
    Generate a streaming response from OpenAI with retry logic and character-by-character streaming.
    
    Args:
        messages: List of message dicts with role and content
        model: The model to use
        system_prompt: Optional system prompt to prepend
        character_streaming: If True, stream character-by-character for smoother UX (like ChatGPT)
    
    Yields:
        Chunks of the response content (character-by-character if character_streaming=True)
    """
    full_messages = []
    
    # Add system prompt if provided
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    
    full_messages.extend(messages)
    
    try:
        stream = await _create_chat_completion_with_retry(model, full_messages)
        
        if character_streaming:
            # Buffer for character-by-character streaming
            buffer = ""
            import asyncio
            total_chars_streamed = 0
            
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and hasattr(delta, 'content') and delta.content:
                        buffer += delta.content
                        
                        # Adaptive streaming: faster for longer responses
                        # Start with smaller chunks for smooth effect, increase speed as response grows
                        if total_chars_streamed < 50:
                            # First 50 chars: slower, more visible typing effect
                            chunk_size = 2
                            delay = 0.008  # 8ms
                        elif total_chars_streamed < 200:
                            # Next 150 chars: medium speed
                            chunk_size = 3
                            delay = 0.005  # 5ms
                        else:
                            # After 200 chars: faster streaming for efficiency
                            chunk_size = 4
                            delay = 0.003  # 3ms
                        
                        # Stream characters in adaptive chunks
                        while len(buffer) >= chunk_size:
                            chunk_to_send = buffer[:chunk_size]
                            buffer = buffer[chunk_size:]
                            total_chars_streamed += len(chunk_to_send)
                            yield chunk_to_send
                            # Adaptive delay for smooth typing effect (ChatGPT-like)
                            await asyncio.sleep(delay)
            
            # Send remaining buffer
            if buffer:
                yield buffer
        else:
            # Original chunk-based streaming (faster but less smooth)
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and hasattr(delta, 'content') and delta.content:
                        yield delta.content
                
    except Exception as e:
        # If model not found (e.g., gpt-5.2-preview not available), fallback to gpt-4o
        if "model" in str(e).lower() and ("not found" in str(e).lower() or "invalid" in str(e).lower()):
            logger.warning(f"⚠️  Model {model} mevcut değil, gpt-4o'ya fallback yapılıyor")
            logger.info(f"🔄 Model değişikliği: {model} -> gpt-4o")
            try:
                stream = await _primary_client.chat.completions.create(
                    model="gpt-4o",
                    messages=full_messages,
                    stream=True,
                    temperature=0.7,
                    max_tokens=4096,
                )
                logger.info("✅ Fallback model (gpt-4o) başarıyla kullanılıyor")
                async for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and hasattr(delta, 'content') and delta.content:
                            yield delta.content
            except Exception as fallback_error:
                logger.error(f"❌ Fallback hatası: {fallback_error}", exc_info=True)
                error_msg = format_error(OPENAI_API_ERROR)
                yield error_msg
        else:
            logger.error(f"Generation error: {e}", exc_info=True)
            if isinstance(e, RateLimitError):
                error_msg = format_error(OPENAI_RATE_LIMIT)
            elif isinstance(e, APITimeoutError):
                error_msg = format_error(OPENAI_TIMEOUT)
            else:
                error_msg = format_error(OPENAI_API_ERROR)
            yield error_msg


async def generate_summary(messages: list[dict]) -> str:
    """
    Generate a summary of the conversation for context management.
    """
    summary_prompt = """Summarize the key points of this conversation in 2-3 sentences. 
Focus on the main topics discussed, any decisions made, and important context that would be 
needed to continue the conversation later."""
    
    # Format messages for summary
    conversation = "\n".join([
        f"{m['role'].upper()}: {m['content']}" 
        for m in messages
    ])
    
    try:
        response = await _primary_client.chat.completions.create(
            model=settings.simple_model,
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": conversation}
            ],
            max_tokens=200,
            temperature=0.3,
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        logger.error(f"Summary error: {e}", exc_info=True)
        return ""


def detect_language(message: str) -> str:
    """
    Detect the primary language of a message using simple heuristics.
    Returns language code: 'tr', 'en', or 'auto' (default to user's language).
    """
    message_lower = message.lower()
    
    # Turkish character patterns
    turkish_chars = ['ç', 'ğ', 'ı', 'ö', 'ş', 'ü']
    turkish_words = ['bir', 'bu', 'şu', 've', 'ile', 'için', 'var', 'yok', 'nasıl', 'ne', 'neden', 
                     'merhaba', 'selam', 'teşekkür', 'sağol', 'evet', 'hayır', 'tamam', 'olur']
    
    # Count Turkish indicators
    turkish_char_count = sum(1 for char in message_lower if char in turkish_chars)
    turkish_word_count = sum(1 for word in turkish_words if word in message_lower)
    
    # If message has Turkish characters or common Turkish words, it's likely Turkish
    if turkish_char_count > 0 or turkish_word_count >= 2:
        return 'tr'
    
    # Check for common English patterns
    english_words = ['the', 'and', 'is', 'are', 'was', 'were', 'this', 'that', 'with', 'for', 
                     'hello', 'hi', 'thanks', 'thank', 'yes', 'no', 'ok', 'okay', 'how', 'what', 'why']
    english_word_count = sum(1 for word in english_words if word in message_lower)
    
    if english_word_count >= 2:
        return 'en'
    
    # Default: let AI decide based on context
    return 'auto'


def detect_message_type(message: str) -> str:
    """
    Detect the type of message to determine appropriate response style.
    Returns: 'academic', 'casual', 'technical', 'creative', or 'general'
    """
    message_lower = message.lower()
    
    # Academic/educational keywords
    academic_keywords = [
        'ders', 'konu', 'öğren', 'açıkla', 'anlat', 'nedir', 'nasıl çalışır',
        'formül', 'hesapla', 'çöz', 'soru', 'problem', 'örnek', 'tanım',
        'lesson', 'explain', 'how does', 'what is', 'calculate', 'solve',
        'formula', 'equation', 'theorem', 'concept', 'theory', 'define'
    ]
    
    # Technical keywords
    technical_keywords = [
        'kod', 'program', 'algoritma', 'fonksiyon', 'class', 'function',
        'code', 'programming', 'algorithm', 'debug', 'error', 'bug',
        'api', 'database', 'server', 'framework'
    ]
    
    # Creative keywords
    creative_keywords = [
        'yaz', 'şiir', 'hikaye', 'öykü', 'yarat', 'tasarla',
        'write', 'poem', 'story', 'creative', 'design', 'imagine'
    ]
    
    academic_score = sum(1 for kw in academic_keywords if kw in message_lower)
    technical_score = sum(1 for kw in technical_keywords if kw in message_lower)
    creative_score = sum(1 for kw in creative_keywords if kw in message_lower)
    
    if academic_score >= 2 or academic_score >= 1 and len(message) > 30:
        return 'academic'
    elif technical_score >= 2:
        return 'technical'
    elif creative_score >= 2:
        return 'creative'
    elif any(word in message_lower for word in ['merhaba', 'selam', 'hello', 'hi', 'nasılsın', 'how are']):
        return 'casual'
    else:
        return 'general'


def get_system_prompt(user_message: str, conversation_history: list[dict] = None) -> str:
    """
    Generate an advanced system prompt based on user's language, message type, and context.
    Uses advanced prompt engineering techniques: Chain of Thought, Few-Shot principles, adaptive styling.
    
    Args:
        user_message: The current user message
        conversation_history: Previous messages in the conversation (optional)
    
    Returns:
        Highly optimized system prompt string
    """
    # Detect language and message type
    language = detect_language(user_message)
    message_type = detect_message_type(user_message)
    
    # If we have conversation history, check previous messages too
    if conversation_history:
        for msg in reversed(conversation_history[-3:]):  # Check last 3 messages
            if msg.get('role') == 'user':
                detected = detect_language(msg.get('content', ''))
                if detected != 'auto':
                    language = detected
                msg_type = detect_message_type(msg.get('content', ''))
                if msg_type != 'general':
                    message_type = msg_type
                    break
    
    # Base prompt with advanced principles
    base_prompt = """You are Chatow, an exceptionally intelligent and helpful AI assistant with advanced reasoning capabilities.

CORE INTELLIGENCE PRINCIPLES:
- Use Chain of Thought reasoning: Break down complex problems into steps, think through each step logically
- Provide deep, thorough analysis when needed - don't just give surface-level answers
- Always include concrete examples when explaining concepts - examples make understanding easier
- Adapt your explanation depth to the user's apparent knowledge level
- Be accurate, precise, and cite reasoning when possible
- If uncertain, acknowledge it and explain your reasoning process"""

    # Academic/Educational responses - Deep analysis with examples
    if message_type == 'academic':
        academic_instructions = """

ACADEMIC/EDUCATIONAL RESPONSES (High Priority):
When answering academic or educational questions, follow this structure:
1. **Clear Definition**: Start with a concise, accurate definition
2. **Deep Analysis**: Break down the concept into its components using Chain of Thought
   - What are the key elements?
   - How do they relate to each other?
   - Why is this important?
3. **Concrete Examples**: Always provide 2-3 real-world examples
   - Simple example first
   - More complex example if applicable
   - Relate examples to the user's context when possible
4. **Step-by-Step Explanation**: For problems, show your work step by step
5. **Visual Aids**: Use formatting (bullet points, numbered lists, code blocks) to make it clear
6. **Connections**: Link to related concepts if relevant
7. **Practice Application**: Suggest how to apply this knowledge

Emoji usage: Minimal - only use relevant educational emojis (📚📐🔬💡) sparingly, maximum 1-2 per response."""
    
    # Technical responses
    elif message_type == 'technical':
        academic_instructions = """

TECHNICAL/CODING RESPONSES:
- Provide clear, working code examples
- Explain the logic step by step
- Include error handling and best practices
- Use code blocks with proper formatting
- Explain both "what" and "why"
- Provide alternative approaches when relevant

Emoji usage: Minimal - only use relevant tech emojis (💻⚙️🔧) sparingly."""
    
    # Creative responses
    elif message_type == 'creative':
        academic_instructions = """

CREATIVE RESPONSES:
- Be imaginative and expressive
- Use vivid language and descriptions
- Encourage creativity in the user
- Provide multiple creative options when possible

Emoji usage: Moderate - use emojis that enhance the creative expression (🎨✨🌟📝), 2-4 per response."""
    
    # Casual conversation
    elif message_type == 'casual':
        academic_instructions = """

CASUAL CONVERSATION:
- Be warm, friendly, and engaging
- Match the user's energy and tone
- Keep it light and conversational
- Show personality

Emoji usage: Natural - use emojis naturally to express warmth and friendliness (😊👍💬), 2-5 per response as appropriate."""
    
    # General responses
    else:
        academic_instructions = """

GENERAL RESPONSES:
- Balance thoroughness with conciseness
- Adapt style to the question's complexity
- Use examples when helpful
- Be clear and direct

Emoji usage: Contextual - use emojis when they add value (😊💡✅), 1-3 per response as appropriate."""

    # Language-specific adaptations
    if language == 'tr':
        lang_instructions = """

LANGUAGE & TONE (Turkish):
- Respond naturally in Turkish
- Use friendly, conversational tone ("sen" form when appropriate)
- Match user's formality level
- Use natural Turkish expressions and idioms
- Be culturally aware and contextually appropriate"""
    
    elif language == 'en':
        lang_instructions = """

LANGUAGE & TONE (English):
- Respond in clear, natural English
- Match user's formality level
- Use appropriate tone for context
- Be culturally aware"""
    
    else:
        lang_instructions = """

LANGUAGE ADAPTATION:
- Detect and respond in the user's language
- Match their tone and formality
- Follow their language mixing if they do"""

    # Emoji usage guidelines (universal)
    emoji_guidelines = """

EMOJI USAGE GUIDELINES (Apply to all responses):
- Use emojis thoughtfully - they should enhance understanding, not distract
- Academic/technical content: Minimal (0-2 emojis)
- Casual conversation: Natural (2-5 emojis)
- Creative content: Moderate (2-4 emojis)
- Never overuse emojis - quality over quantity
- Choose emojis that are contextually relevant
- Avoid emojis in formal explanations unless they clarify a point"""

    # Combine all parts
    full_prompt = base_prompt + academic_instructions + lang_instructions + emoji_guidelines
    
    return full_prompt


async def generate_title(first_message: str) -> str:
    """
    Generate a short title for a chat session based on the first message.
    """
    title_prompt = """Generate a very short title (3-5 words) for a conversation that starts with this message. 
Do not use quotes. Just return the title."""
    
    try:
        response = await _primary_client.chat.completions.create(
            model=settings.simple_model,
            messages=[
                {"role": "system", "content": title_prompt},
                {"role": "user", "content": first_message}
            ],
            max_tokens=20,
            temperature=0.7,
        )
        
        title = response.choices[0].message.content.strip()
        # Limit length
        return title[:50] if len(title) > 50 else title
    
    except Exception as e:
        logger.error(f"Title generation error: {e}", exc_info=True)
        return "New Chat"
