import json
import logging
import os

from django.conf import settings

from assistant.bot.domain import NoResourceFound, NoMessageFound

logger = logging.getLogger(__name__)


class ResourceManager:

    def __init__(self, codename: str, language: str, default_language: str = getattr(settings, 'BOT_DEFAULT_LANGUAGE', 'ru')):
        self.codename = codename
        self.language = language
        self.default_language = default_language

    def get_resource(self, path):
        file_path = os.path.join(settings.RESOURCES_DIR, self.codename, path)
        try:
            logger.debug(f'Get resource {file_path}')
            with open(file_path, 'r') as file:
                content = file.read()
        except FileNotFoundError:
            raise NoResourceFound(file_path)
        return content

    def get_prompt(self, path):
        return self.get_resource(f'prompts/{path}')

    def get_message(self, path):
        try:
            return self.get_resource(f'messages/{self.language}/{path}')
        except NoResourceFound as e:
            logger.warning(f'Failed to get message {path} for language {self.language}: {e}')
            try:
                return self.get_resource(f'messages/{self.default_language}/{path}')
            except NoResourceFound as e:
                raise NoMessageFound(str(e))

    def get_phrase(self, phrase: str):
        try:
            phrases = self.get_resource(f'phrases/{self.language}.json')
        except NoResourceFound as e:
            logger.warning(f'Failed to get phrases for language {self.language}: {e}')
            try:
                return self.get_resource(f'phrases/{self.default_language}.json')
            except NoResourceFound as e:
                logger.warning(f'Failed to get phrases for language {self.default_language}: {e}')
                phrases = "{}"
        try:
            phrases_data = json.loads(phrases)
        except json.JSONDecodeError:
            logger.exception('Failed to parse phrases')
            phrases_data = {}
        return phrases_data.get(phrase, phrase)


