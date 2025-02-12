import asyncio

from django.core.management import BaseCommand

from assistant.bot.models import Bot
from assistant.loading.csv import CSVLoader


class Command(BaseCommand):
    help = 'Load data from csv file'

    def add_arguments(self, parser):
        parser.add_argument('file', type=str)
        parser.add_argument('--bot', type=str, required=True, help='Bot name')

    def handle(self, *args, **options):
        bot = Bot.objects.get(codename=options['bot'])
        loader = CSVLoader(bot, filepath=options['file'])
        asyncio.run(loader.load())
