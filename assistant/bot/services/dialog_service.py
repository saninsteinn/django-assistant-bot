import base64
import io
from datetime import timedelta, datetime
from typing import List, Dict, Optional
from urllib.parse import urljoin

from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone

from assistant.ai.services.ai_service import calculate_ai_cost
from assistant.ai.domain import Message as GPTMessage
from assistant.bot.domain import logger, SingleAnswer, Photo
from assistant.bot.models import Dialog, Role, Message, Instance


def get_gpt_messages(dialog: Dialog, system_text: str, last_message_id: int = None) -> List[GPTMessage]:
    messages = [
       {'role': 'system', 'content': system_text},
    ] if system_text else []
    # has_text = False

    for message in dialog.messages.select_related('role').order_by('timestamp'):
        if last_message_id and message.id > last_message_id:
            continue

        if message.text and message.text == '/continue':
            messages.append(
                {'role': 'system', 'content': 'Continue'}
            )
            continue

        images = None
        if message.photo:
            # image_url = urljoin(settings.MEDIA_URL, message.photo.url)
            # logger.info('Image URL: %s', image_url)
            images = [
                base64.b64encode(message.photo.read()).decode('utf-8')
            ]

        messages.append(
            {'role': message.role.name, 'content': message.text, 'images': images}
        )

    # if not has_text and dialog.instance.language:
    #     messages.append(
    #         GPTMessage(
    #             role='system',
    #             content=f'User language: `{dialog.instance.language}`. Answer in this language.'
    #         )
    #     )

    # sum_len = sum(len(m['content']) for m in messages)
    # doc_cut = False
    # while sum_len > 8000 and len(messages) > 3:
    #     logger.info('sum_len = %s', sum_len)
    #     doc_cut = True
    #     message_len = len(messages[1]['content'])
    #     sum_len -= message_len
    #     logger.info('del message with len %s', message_len)
    #     del messages[1]
    # if doc_cut:
    #     messages.insert(1, GPTMessage(
    #         role='system',
    #         content='Some old user messages are missing'
    #     ))
    return messages


def get_dialog(instance: Instance, ttl: timedelta = None):
    last_message = Message.objects.filter(
        dialog__instance=instance, dialog__is_completed=False
    ).prefetch_related('dialog__instance', 'dialog__instance__bot', 'dialog__instance__user').order_by('-timestamp').first()
    if last_message and (ttl is None or last_message.timestamp > timezone.now() - ttl):
        dialog = last_message.dialog
    else:
        if last_message:
            last_message.dialog.is_completed = True
            last_message.dialog.save(update_fields=['is_completed'])
        dialog = Dialog.objects.create(instance=instance)
    return dialog


def get_last_message(dialog: Dialog) -> Optional[Message]:
    last_message = Message.objects.filter(
        dialog=dialog
    ).order_by('-timestamp').first()
    return last_message


def create_user_message(dialog: Dialog, message_id: int, text: str = None, photo: Photo = None) -> Message:
    user_role, _ = Role.objects.get_or_create(name='user')

    photo_file: ContentFile = None
    if photo:
        image_file = io.BytesIO(photo.content)
        logger.debug(f'Image file size: {len(image_file.getvalue())}')
        # Create InMemoryUploadedFile
        photo_file = ContentFile(
            image_file.getvalue(),
            name=f"{photo.file_id}.{photo.extension}"
        )

    m, _ = Message.objects.get_or_create(
        dialog=dialog,
        message_id=message_id,
        role=user_role,
        defaults={
            'text': text,
            'photo': photo_file
        }
    )
    return m


def create_bot_message(dialog: Dialog, answer: SingleAnswer):
    assistant_role, _ = Role.objects.get_or_create(name='assistant')
    Message.objects.get_or_create(
        dialog=dialog,
        role=assistant_role,
        text=answer.raw_text,
        cost_details=answer.usage,
        cost=sum(calculate_ai_cost(u) for u in answer.usage),
    )


def have_existing_answers(user_message: Message) -> bool:
    return Message.objects.filter(
        dialog=user_message.dialog,
        role__name='assistant',
        id__gt=user_message.id
    ).exists()
