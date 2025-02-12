import os
from typing import Union, List


class JSONSchema:

    def __init__(self, schemas_dir: str):
        self._schemas_dir = schemas_dir

    def get_schema(self, name: str):
        """Get the JSON schema for the given name."""
        with open(os.path.join(self._schemas_dir, f'{name}.json')) as f:
            json_schema = f.read().strip()
        json_schema = ("```json\n"
                       f"{json_schema}\n"
                       "```\n")
        return json_schema

    def get_prompt(self, schema: Union[str, List[str]], do_escape=False):
        """Get the JSON prompt for the given schema."""
        if isinstance(schema, list):
            json_schemas = [self.get_schema(s) for s in schema]
            return (
                "Answer with a JSON response that strictly matches one of the following examples:\n"
                f"{''.join(json_schemas)}"
            ) + (f"Do not forget to escape special characters in the JSON like \\n.\n" if do_escape else "")
        else:
            json_schema = self.get_schema(schema)
            return (
                "Answer with a JSON response that strictly matches the following example:\n"
                f"{json_schema}"
            ) + (f"Do not forget to escape special characters in the JSON like \\n.\n" if do_escape else "")

