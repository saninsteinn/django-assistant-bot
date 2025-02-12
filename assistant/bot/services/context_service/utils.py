from typing import List
from assistant.ai.domain import Message


def add_system_message(messages: List[Message], content: str) -> List[Message]:
    """
    Adds a system message to the messages.
    """
    # system_messages = [
    #     m for m in messages if m['role'] == 'system'
    # ]
    # system_messages.append(
    #     Message(role='system', content=content)
    # )
    # no_system_messages = [
    #     m for m in messages if m['role'] != 'system'
    # ]
    #
    # system_message_merged = {
    #     'role': 'system',
    #     'content': '\n----------\n'.join([m['content'] for m in system_messages])
    # }
    #
    # messages = [system_message_merged] + no_system_messages
    messages = messages + [Message(role='system', content=content)]

    return messages


def get_list_str(items: List[str]) -> str:
    """
    Get the Table of Contents for the given parent.
    """
    text = ''
    text += '\n'.join([
        f'- {s}'
        for s in items
    ])
    return text


def get_numerical_list_str(items: List[str]) -> str:
    """
    Get the Table of Contents for the given parent.
    """
    text = ''
    text += '\n'.join([
        f'{i + 1}. `{s}`'
        for i, s in enumerate(items)
    ])
    return text
