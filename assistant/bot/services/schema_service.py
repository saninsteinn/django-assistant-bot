import os

from assistant.utils.json_schema import JSONSchema

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'schemas')

_json_schema = JSONSchema(SCHEMA_DIR)


def json_prompt(name: str, *args, **kwargs):
    return _json_schema.get_prompt(name, *args, **kwargs)
