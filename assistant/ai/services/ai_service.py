import logging
import re
from decimal import Decimal
from typing import Dict

from django.conf import settings

from assistant.ai.providers.base import AIProvider, AIEmbedder
from assistant.ai.providers.gpu_service import GPUServiceProvider

logger = logging.getLogger(__name__)


def get_ai_provider(model: str) -> AIProvider:
    logger.debug(f'Getting AI provider for model: {model}')
    if model.startswith('groq:'):
        from assistant.ai.providers.groq import GroqAIProvider
        provider = GroqAIProvider(
            model=model[len('groq:'):],
            api_key=settings.GROQ_API_KEY,
        )
    elif model.startswith('gpu_service:'):
        model = model[len('gpu_service:'):]
        from assistant.ai.embedders.gpu_service import GPUServiceEmbedder
        provider = GPUServiceProvider(
            base_url=settings.GPU_SERVICE_ENDPOINT,
            model=model
        )
    elif model.startswith('llama'):
        from assistant.ai.providers.ollama import OllamaAIProvider
        provider = OllamaAIProvider(
            model=model,
            host=settings.OLLAMA_ENDPOINT
        )
    elif model.startswith('ollama:'):
        model = model[len('ollama:'):]
        from assistant.ai.providers.ollama import OllamaAIProvider
        provider = OllamaAIProvider(
            model=model,
            host=settings.OLLAMA_ENDPOINT
        )
    else:
        from assistant.ai.providers.openai import ChatGPTAIProvider
        provider = ChatGPTAIProvider(
            model=model,
            api_key=settings.OPENAI_API_KEY,
        )
    return provider


def get_ai_embdedder(model: str = None) -> AIEmbedder:
    if not model:
        model = 'nomic-embed-text'

    if model.startswith('text-embedding-3'):
        from assistant.ai.embedders.openai import ChatGPTEmbedder
        embedder = ChatGPTEmbedder(
            model=model,
            api_key=settings.OPENAI_API_KEY,
        )
    elif model.startswith('gpu_service:'):
        model = model[len('gpu_service:'):]
        from assistant.ai.embedders.gpu_service import GPUServiceEmbedder
        embedder = GPUServiceEmbedder(
            base_url=settings.GPU_SERVICE_ENDPOINT,
            model=model
        )
    else:
        from assistant.ai.embedders.ollama import OllamaEmbedder
        embedder = OllamaEmbedder(
            model=model,
            host=settings.OLLAMA_ENDPOINT,
        )
    return embedder


def extract_tagged_text(text):
    # Adjusting the regex pattern to handle tags at the beginning and in the middle of the text
    pattern = r'#(\w+)\s?(.*?)(?=\s#|$)'

    # Using findall to extract all matches
    matches = re.findall(pattern, text, re.DOTALL)

    # Creating a dictionary from the matches
    tagged_text = {tag.lower(): text.strip() for tag, text in matches}
    return tagged_text


def calculate_ai_cost(usage: Dict) -> Decimal:
    model = usage['model']
    if model == 'dall-e-3':
        size = usage['size']
        quality = usage['quality']
        n = usage['n']
        cost = {
            ('1024x1024', 'standard'): Decimal('0.04'),
            ('1024×1792', 'standard'): Decimal('0.08'),
            ('1792×1024', 'standard'): Decimal('0.08'),
            ('1024x1024', 'hd'): Decimal('0.08'),
            ('1024×1792', 'hd'): Decimal('0.12'),
            ('1792×1024', 'hd'): Decimal('0.12'),
        }[(size, quality)] * n
    elif model.startswith('gpt-3.5-turbo'):
        prompt_tokens = usage['prompt_tokens']
        completion_tokens = usage['completion_tokens']
        cost = (
                (Decimal('0.001') * prompt_tokens * Decimal('0.001')) +
                (Decimal('0.001') * completion_tokens * Decimal('0.002'))
        )
    elif model.startswith('gpt-4-'):
        prompt_tokens = usage['prompt_tokens']
        completion_tokens = usage['completion_tokens']
        cost = (
                (Decimal('0.001') * prompt_tokens * Decimal('0.01')) +
                (Decimal('0.001') * completion_tokens * Decimal('0.03'))
        )
    elif model.startswith('llama'):
        cost = 0
    else:
        logger.warning(f'Unknown model: {model}')
        cost = 0
    return cost

