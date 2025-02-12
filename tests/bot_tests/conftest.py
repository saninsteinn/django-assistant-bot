import pytest

from tests.bot_tests.factories import BotFactory, InstanceFactory, DialogFactory, MessageFactory, RoleFactory


@pytest.fixture
def bot():
    return BotFactory()


@pytest.fixture
def instance(bot):
    return InstanceFactory(bot=bot)


@pytest.fixture
def other_instance():
    return InstanceFactory()


@pytest.fixture
def dialog(instance):
    dialog = DialogFactory(instance=instance)
    return dialog


@pytest.fixture
def other_dialog(other_instance):
    return DialogFactory(instance=other_instance)


@pytest.fixture
def user_message(dialog):
    return MessageFactory(dialog=dialog)


@pytest.fixture
def assistant_message(dialog):
    return MessageFactory(dialog=dialog, role=RoleFactory(name='assistant'))
