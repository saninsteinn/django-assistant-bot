import os

from assistant.utils.json_schema import JSONSchema


SCHEMA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'schemas')

_json_schema = JSONSchema(SCHEMA_DIR)


def json_prompt(name: str, *args, **kwargs):
    return _json_schema.get_prompt(name, *args, **kwargs)


def split_text_by_parts(text: str, max_part_length: int):
    """
    Split the document by newlines so that each part does not exceed the specified length.
    """
    parts = []
    part = ''
    for line in text.splitlines():
        if len(part) + len(line) > max_part_length:
            parts.append(part)
            part = ''
        part += line + '\n'
    if part:
        parts.append(part)
    return parts
