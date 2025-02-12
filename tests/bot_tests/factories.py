from contextlib import contextmanager

import factory
from django.db.models.signals import post_save

from assistant.bot.models import Dialog, Message, Instance, Bot, Role, BotUser


@contextmanager
def disable_signals(signal):
    """Context manager to temporarily disable a Django signal"""
    signal.receivers = []
    try:
        yield
    finally:
        signal.receivers = []


class BotFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Bot

    codename = factory.Sequence(lambda n: f'bot{n}')
    telegram_token = factory.Sequence(lambda n: f'token{n}')

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override the default create method to disable signals"""
        with disable_signals(post_save):
            return super()._create(model_class, *args, **kwargs)


class BotUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BotUser

    user_id = factory.Sequence(lambda n: f'user{n}')
    platform = 'api'
    username = factory.Sequence(lambda n: f'username{n}')
    language = 'en'


class InstanceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Instance

    bot = factory.SubFactory(BotFactory)
    user = factory.SubFactory(BotUserFactory)


class RoleFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = Role

    name = factory.Iterator(['user', 'assistant'])


class DialogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Dialog

    instance = factory.SubFactory(InstanceFactory)


class MessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Message

    dialog = factory.SubFactory(DialogFactory)
    role = factory.SubFactory(RoleFactory)
    text = factory.Sequence(lambda n: f'Message content {n}')
