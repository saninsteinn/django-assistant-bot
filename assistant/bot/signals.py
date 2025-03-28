import logging

import requests
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from assistant.bot.models import Bot


logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Bot)
def bot_pre_save(sender, instance, **kwargs):
    logger.info(f'Bot pre_save signal for {instance}')
    if instance.pk:
        try:
            instance._original_instance = Bot.objects.get(pk=instance.pk)
        except Bot.DoesNotExist:
            instance._original_instance = None
    else:
        instance._original_instance = None


@receiver(post_save, sender=Bot)
def bot_post_save(sender, instance, created, **kwargs):
    logger.info(f'Bot post_save signal for {instance}')
    if (created or
            instance.telegram_token != instance._original_instance.telegram_token or
            instance.callback_url != instance._original_instance.callback_url
    ):
        if instance.callback_url:
            logging.info(f'Setting webhook {instance.callback_url} for bot {instance.codename}')
            _set_webhook(instance.telegram_token, instance.callback_url)
        else:
            logging.info(f'Skipping webhook setup for bot {instance.codename} - callback_url is not set')
    else:
        logging.debug(f'Webhook for bot {instance.codename} is already set')


def _set_webhook(telegram_token: str, url: str):
    telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/setWebhook"
    response = requests.post(telegram_api_url, data={'url': url}, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Telegram API error: {response.text}")
