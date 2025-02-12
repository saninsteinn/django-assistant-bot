# tests/test_api.py
import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token

from assistant.bot.domain import SingleAnswer
from .factories import DialogFactory, MessageFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    client = APIClient()
    # client.login(username=user.username, password='testpass')
    return client


@pytest.fixture
def api_client_with_token(api_client, django_user_model):
    # Create test user
    user = django_user_model.objects.create_user(username='testuser', password='testpass')
    token = Token.objects.create(user=user)
    api_client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    return api_client


@pytest.fixture
def unauthenticated_client():
    return APIClient()


# Tests for DialogViewSet
def test_list_dialogs(api_client_with_token, dialog, other_dialog):
    response = api_client_with_token.get(reverse('dialog-list'))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    assert data[0]['id'] == str(dialog.id)
    assert data[1]['id'] == str(other_dialog.id)


def test_create_dialog(api_client_with_token, bot):
    data = {
        'bot': bot.codename,
    }
    response = api_client_with_token.post(reverse('dialog-list'), data)
    assert response.status_code == status.HTTP_201_CREATED, response.json()
    data = response.json()
    assert 'id' in data
    dialog_id = data['id']
    dialog = DialogFactory._meta.model.objects.get(id=dialog_id)
    assert dialog is not None
    assert dialog.instance.bot.codename == bot.codename
    assert dialog.instance.user.user_id == str(dialog.id)
    assert dialog.instance.user.username is None


def test_create_dialog_with_user(api_client_with_token, bot):
    data = {
        'bot': bot.codename,
        'user': {
            'user_id': '123',
            'username': 'testuser',
        }
    }
    response = api_client_with_token.post(reverse('dialog-list'), data, format='json')
    assert response.status_code == status.HTTP_201_CREATED, response.json()
    data = response.json()
    assert 'id' in data
    dialog_id = data['id']
    dialog = DialogFactory._meta.model.objects.get(id=dialog_id)
    assert dialog is not None
    assert dialog.instance.bot.codename == bot.codename
    assert dialog.instance.user.user_id == '123'
    assert dialog.instance.user.username == 'testuser'


def test_retrieve_dialog(api_client_with_token, dialog):
    response = api_client_with_token.get(reverse('dialog-detail', kwargs={'pk': dialog.id}))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data['id'] == str(dialog.id)


def test_update_dialog(api_client_with_token, dialog):
    response = api_client_with_token.patch(reverse('dialog-detail', kwargs={'pk': dialog.id}), {'is_completed': True})
    assert response.status_code == status.HTTP_200_OK
    dialog = DialogFactory._meta.model.objects.get(id=dialog.id)
    assert dialog.is_completed is True


def test_delete_dialog(api_client_with_token, dialog):
    response = api_client_with_token.delete(reverse('dialog-detail', kwargs={'pk': dialog.id}))
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not DialogFactory._meta.model.objects.filter(id=dialog.id).exists()


# Tests for MessageViewSet
def test_list_messages(api_client_with_token, dialog, user_message, assistant_message):
    response = api_client_with_token.get(reverse('dialog-messages-list', kwargs={'dialog_pk': dialog.id}))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 2
    message_ids = [message['id'] for message in data]
    assert user_message.id in message_ids
    assert assistant_message.id in message_ids


def test_create_message(api_client_with_token, dialog, mocker):
    mocker.patch(
        'assistant.bot.assistant_bot.AssistantBot.get_answer_to_messages',
        return_value=SingleAnswer(text='Assistant answer')
    )
    response = api_client_with_token.post(reverse('dialog-messages-list', kwargs={'dialog_pk': dialog.id}),
                                          {'text': 'How are you?'})
    assert response.status_code == status.HTTP_201_CREATED, response.json()
    data = response.json()
    message_id = data['id']
    message = MessageFactory._meta.model.objects.get(id=message_id)
    assert message.role.name == 'user'
    assert message.text == 'How are you?'
    assistant_message = MessageFactory._meta.model.objects.filter(dialog=dialog, role__name='assistant').latest('timestamp')
    assert assistant_message.text == "Assistant answer"


def test_retrieve_message(api_client_with_token, dialog, user_message):
    response = api_client_with_token.get(reverse('dialog-messages-detail', kwargs={'dialog_pk': dialog.id, 'pk': user_message.id}))
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data['id'] == user_message.id


def test_update_message(api_client_with_token, dialog, user_message):
    response = api_client_with_token.put(reverse('dialog-messages-detail', kwargs={'dialog_pk': dialog.id, 'pk': user_message.id}),
                                         {'text': 'Updated text'})
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_delete_message(api_client_with_token, dialog, user_message):
    response = api_client_with_token.delete(reverse('dialog-messages-detail', kwargs={'dialog_pk': dialog.id, 'pk': user_message.id}))
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
