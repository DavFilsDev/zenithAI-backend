from google import genai
from google.genai import types
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class GeminiService:
    # Updated to current stable free-tier models (April 2026)
    AVAILABLE_MODELS = {
        "gemini-2.5-flash": "gemini-2.5-flash",     # Best free tier: fast + smart
        "gemini-2.5-pro": "gemini-2.5-pro",         # Best reasoning/coding (lower quota)
        "gemini-2.5-flash-lite": "gemini-2.5-flash-lite",  # Ultra-fast, lightweight
    }

    # System prompt that makes the model better at helping learners with code
    CODING_SYSTEM_PROMPT = """You are a helpful AI assistant specialized in programming and software development.
When answering coding questions:
- Provide clear, well-commented code examples
- Explain *why* the code works, not just what it does
- Point out common mistakes and how to avoid them
- Suggest best practices for the language or framework being used
Be concise, friendly, and educational in tone."""

    def __init__(self):
        try:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
            self.model_name = settings.GEMINI_MODEL
            self.available = True
            logger.info(f"Gemini AI initialized with model: {self.model_name}")
            self._test_connection()
        except Exception as e:
            self.available = False
            logger.error(f" Failed to initialize Gemini: {str(e)}")

    def _test_connection(self):
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents="Hi",
                config=types.GenerateContentConfig(max_output_tokens=5),
            )
            logger.info(f" Connection test successful: {self.model_name}")
        except Exception as e:
            logger.warning(f" Model test failed: {str(e)}")

    def generate_response(self, message, conversation_history=None):
        if not self.available:
            return " AI service is currently unavailable. Please try again later."

        try:
            # Build the conversation as a single prompt with history context
            if conversation_history:
                context_parts = []
                for msg in conversation_history:
                    role_label = "User" if msg["role"] == "user" else "Assistant"
                    context_parts.append(f"{role_label}: {msg['content']}")
                context_parts.append(f"User: {message}")
                prompt = "\n".join(context_parts)
            else:
                prompt = message

            logger.info(f"Generating response with model: {self.model_name}")

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.CODING_SYSTEM_PROMPT,
                    temperature=settings.GEMINI_CONFIG.get("temperature", 0.7),
                    max_output_tokens=settings.GEMINI_CONFIG.get("max_output_tokens", 2048),
                    top_p=settings.GEMINI_CONFIG.get("top_p", 0.95),
                    top_k=settings.GEMINI_CONFIG.get("top_k", 40),
                ),
            )

            return response.text

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gemini API error: {error_msg}")

            if "404" in error_msg:
                return (
                    f" Model '{self.model_name}' not found. "
                    "Check that your model name is correct (e.g. 'gemini-2.5-flash')."
                )
            elif "API key" in error_msg or "403" in error_msg:
                return " Invalid API key. Please check your GEMINI_API_KEY in settings."
            elif "429" in error_msg:
                return " Rate limit reached on the free tier. Please wait a moment and try again."
            else:
                return f" Sorry, I encountered an error: {error_msg[:200]}"


# Singleton instance used across the app
gemini_service = GeminiService()