
import asyncio
import logging

from django.core.management import BaseCommand

from assistant.ai.services.ai_service import get_ai_embdedder
from assistant.rag.services.search_service import embeddings_similarity

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Embed documents'

    def add_arguments(self, parser):
        parser.add_argument('query1', type=str, help='Search query 1')
        parser.add_argument('query2', type=str, help='Search query 2')
        parser.add_argument('--model', default='nomic-embed-text', type=str, help='Model')

    def handle(self, *args, **options):
        embedder = get_ai_embdedder(options['model'])
        embeddings = asyncio.run(
            embedder.embeddings([options['query1'], options['query2']])
        )
        # print(f'Embeddings for query 1: {embeddings[0]}')
        # print(f'Embeddings for query 2: {embeddings[1]}')

        score = embeddings_similarity(embeddings[0], embeddings[1])

        print(f'Score: {score}')

