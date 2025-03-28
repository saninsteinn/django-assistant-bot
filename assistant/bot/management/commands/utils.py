from assistant.bot.domain import User
from assistant.bot.models import Bot, BotUser, Instance


def get_instance(codename: str, platform_codename: str, chat_id: str, user: User):
    bot, _ = Bot.objects.get_or_create(codename=codename)

    language = user.language_code if user else None
    username = _get_username(user) if user else None

    bot_user, _ = BotUser.objects.get_or_create(
        user_id=chat_id,
        platform=platform_codename,
        defaults={
            'username': username,
            'language': language,
        }
    )
    if bot_user.language != language:
        bot_user.language = language
        bot_user.save(update_fields=['language'])
    if bot_user.username != username:
        bot_user.username = username
        bot_user.save(update_fields=['username'])

    instance, _ = Instance.objects.get_or_create(
        user_id=bot_user.id,
        bot_id=bot.id,
    )

    instance = Instance.objects.select_related('bot', 'user').get(id=instance.id)
    return instance


# Функция для получения имени пользователя
def _get_username(user: User):
    if user.username:
        return '@' + user.username
    username = ''
    if user.first_name:
        username = user.first_name
    if user.last_name:
        username = f'{username} {user.last_name}'
    if username:
        return username
    return ''
