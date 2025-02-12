
import asyncio

from django.core.management import BaseCommand

from assistant.rag.services.search_service import embedding_search


class Command(BaseCommand):
    help = 'Embed documents'

    def add_arguments(self, parser):
        parser.add_argument('query', type=str, help='Search query')
        # parser.add_argument('--provider', default='llama3:8b', type=str, help='AI provider')
        parser.add_argument('--field', type=str, choices=('sentences', 'questions'), help='Field to search in')
        parser.add_argument('--max-scores-n', default=5, type=int, help='Max scores N')
        parser.add_argument('--n', default=10, type=int, help='Top N documents')

    def handle(self, *args, **options):
        results: list = asyncio.run(
            embedding_search(
                options['query'], max_scores_n=options['max_scores_n'], top_n=options['n'], field=options['field']
            )
        )
        for document, score in results:
            print(f'{document.id}  {score}  ', document.name)
