import logging
import re

import langid


logger = logging.getLogger(__name__)


langid.set_languages(['en', 'ru'])


def get_language(text: str) -> str:
    """
    Check if the text is in the specified language.

    :param text: Text to check
    :return: Detected language
    """
    language, confidence = langid.classify(text)
    logger.debug(f'Detected language: {language} ({confidence}) for text: {text[:100]}...')
    return language


CJK_PATTERN = re.compile(r'[\u4e00-\u9fff'
                         r'\u3040-\u30ff'
                         r'\u3400-\u4dbf'
                         r'\uff00-\uffef'
                         r'\uac00-\ud7af'
                         r'\u1100-\u11ff]')

def has_cjk_characters(text):
    return bool(CJK_PATTERN.search(text))
