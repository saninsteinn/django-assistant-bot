import csv
import logging
import re

from asgiref.sync import sync_to_async
from django.db import transaction

from assistant.bot.models import Bot
from assistant.storage.models import WikiDocument

logger = logging.getLogger(__name__)


class CSVLoader:

    COLUMNS_COUNT = 3

    def __init__(self, bot: Bot, filepath):
        self._bot = bot
        self._filepath = filepath

    async def load(self):
        await (sync_to_async(self._load))()

    @transaction.atomic
    def _load(self):
        with open(self._filepath, 'r') as file:
            reader = csv.reader(file)
            header = next(reader)
            if len(header) != self.COLUMNS_COUNT:
                raise ValueError(f'Invalid columns count: {len(header)}')
            n = 0
            for row in reader:
                toc_title, doc_name, doc_content = row
                parent, _ = WikiDocument.objects.get_or_create(
                    bot=self._bot,
                    title=normalize_title(toc_title),
                    parent=None,
                )
                WikiDocument.objects.create(
                    bot=self._bot,
                    title=normalize_title(doc_name),
                    content=doc_content.strip(),
                    parent=parent
                )
                n += 1
        logger.info(f'Loaded {n} wiki documents')


def normalize_title(name: str):
    name = re.sub(r' +', ' ', name)
    name = name.strip()
    return name
