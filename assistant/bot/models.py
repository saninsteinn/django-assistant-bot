import uuid
from urllib.parse import urljoin

from django.db import models
from django.urls import reverse

from django.conf import settings


class Bot(models.Model):
    codename = models.CharField(max_length=100, unique=True)
    username = models.CharField(max_length=100, null=True, blank=True)
    telegram_token = models.CharField(max_length=100, null=True, blank=True)

    system_text = models.TextField(null=True, blank=True)
    start_text = models.TextField(null=True, blank=True)
    help_text = models.TextField(null=True, blank=True)

    is_whitelist_enabled = models.BooleanField(default=False)
    telegram_whitelist = models.TextField(null=True, blank=True)

    @property
    def callback_url(self):
        base_callback_url = getattr(settings, 'TELEGRAM_BASE_CALLBACK_URL', None)
        if not base_callback_url:
            return None
        if self.codename:
            return urljoin(base_callback_url, reverse('telegram_bot', kwargs={'codename': self.codename}))


class BotUser(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user_id = models.CharField(max_length=100)
    platform = models.CharField(max_length=100)
    username = models.CharField(max_length=100, null=True, blank=True)
    language = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f'<BotUser {self.id} {self.user_id} {self.username}>'

    class Meta:
        unique_together = ('user_id', 'platform')


class Instance(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE)
    user = models.ForeignKey(BotUser, on_delete=models.CASCADE)
    state = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f'<Instance {self.id} {self.bot.codename} {self.user.username}>'


class Dialog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name='dialogs')
    is_completed = models.BooleanField(default=False, db_index=True)
    state = models.JSONField(default=dict, blank=True)


class Role(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Message(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    message_id = models.BigIntegerField(db_index=True, null=True, blank=True)
    dialog = models.ForeignKey(Dialog, related_name='messages', on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    text = models.TextField(null=True, blank=True)
    photo = models.ImageField(upload_to='photos/', null=True, blank=True)
    cost_details = models.JSONField(default=dict, blank=True)
    cost = models.DecimalField(max_digits=16, decimal_places=8, null=True, blank=True)

    class Meta:
        unique_together = ('dialog', 'message_id')
