"""
User-friendly error messages for the API.
All error messages are in English and optimized for better user experience.
"""

# Rate Limiting Errors
RATE_LIMIT_EXCEEDED = (
    "You've reached the rate limit. Please wait a moment before making another request. "
    "You can make up to {max_requests} requests per minute."
)

CONCURRENT_REQUESTS_EXCEEDED = (
    "You have too many active requests. Please wait for your current requests to complete. "
    "Maximum {max_concurrent} concurrent requests allowed."
)

# Credit Errors
INSUFFICIENT_CREDITS = (
    "Insufficient credits. You need {required} credits but only have {available} credits. "
    "Please purchase more credits to continue."
)

# API Errors
OPENAI_RATE_LIMIT = (
    "The AI service is currently experiencing high demand. Please try again in a few moments."
)

OPENAI_API_ERROR = (
    "We're experiencing issues with the AI service. Please try again in a moment. "
    "If the problem persists, contact support."
)

OPENAI_TIMEOUT = (
    "The request took too long to process. Please try again with a shorter message or try later."
)

MODEL_NOT_AVAILABLE = (
    "The requested AI model is temporarily unavailable. We've switched to an alternative model. "
    "Please try again."
)

# Image Generation Errors
IMAGE_GENERATION_ERROR = (
    "We couldn't generate the image. Please check your prompt and try again. "
    "Make sure your prompt follows our content guidelines."
)

IMAGE_GENERATION_TIMEOUT = (
    "Image generation is taking longer than expected. Please try again with a different prompt."
)

# General Errors
INTERNAL_SERVER_ERROR = (
    "An unexpected error occurred. Our team has been notified. "
    "Please try again in a few moments."
)

VALIDATION_ERROR = (
    "Invalid request. Please check your input and try again."
)

UNAUTHORIZED = (
    "You don't have permission to perform this action. Please check your authentication."
)

NOT_FOUND = (
    "The requested resource was not found. It may have been deleted or doesn't exist."
)

MESSAGE_NOT_FOUND = (
    "The message you're looking for doesn't exist or has been deleted."
)

SESSION_NOT_FOUND = (
    "The chat session was not found. It may have been deleted or doesn't exist."
)

# Classification Errors
CLASSIFICATION_ERROR = (
    "We couldn't analyze your message. Using a simpler model to ensure you get a response."
)

# Network Errors
NETWORK_ERROR = (
    "Network connection issue. Please check your internet connection and try again."
)

# Helper function to format error messages
def format_error(template: str, **kwargs) -> str:
    """Format error message template with provided values."""
    try:
        return template.format(**kwargs)
    except KeyError:
        # If formatting fails, return template as-is
        return template


# Error codes for frontend handling
class ErrorCodes:
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    CONCURRENT_REQUESTS_EXCEEDED = "CONCURRENT_REQUESTS_EXCEEDED"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    OPENAI_RATE_LIMIT = "OPENAI_RATE_LIMIT"
    OPENAI_API_ERROR = "OPENAI_API_ERROR"
    OPENAI_TIMEOUT = "OPENAI_TIMEOUT"
    MODEL_NOT_AVAILABLE = "MODEL_NOT_AVAILABLE"
    IMAGE_GENERATION_ERROR = "IMAGE_GENERATION_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    NETWORK_ERROR = "NETWORK_ERROR"
