from django import forms
from django.contrib import admin
from django.db import models
from django.urls import reverse
from django.utils.html import format_html

# from assistant.admin.admin import admin_site
from assistant.bot.models import Bot, Dialog, Message


class BotAdminForm(forms.ModelForm):
    telegram_token = forms.CharField(widget=forms.PasswordInput(render_value=True), required=True)

    class Meta:
        model = Bot
        fields = '__all__'


# @admin.register(Bot, site=admin_site)
class BotAdmin(admin.ModelAdmin):
    form = BotAdminForm

    list_display = ['codename']
    search_fields = ['codename']
    list_filter = ['codename']

    readonly_fields = ['callback_url']
    exclude = ['username']

    actions = None

    def callback_url(self, obj):
        return obj.callback_url
    callback_url.short_description = 'Telegram callback URL'


# @admin.register(Dialog)
class DialogAdmin(admin.ModelAdmin):
    list_display = ('id', 'codename_display', 'instance_display', 'is_completed', 'view_messages')
    list_filter = ['is_completed']
    search_fields = ['instance__system_text']

    def codename_display(self, obj):
        url = reverse('admin:assistant_bot_bot_change', args=[obj.instance.codename])
        return format_html('<a href="{}">{}</a>', url, obj.instance.bot.codename)

    codename_display.short_description = 'Bot'

    def instance_display(self, obj):
        url = reverse('admin:assistant_bot_instance_change', args=[obj.instance.id])
        return format_html('<a href="{}">{}</a>', url, obj.instance.user_id)

    instance_display.short_description = 'Instance'

    def view_messages(self, obj):
        url = reverse('admin:assistant_bot_message_changelist')
        count = Message.objects.filter(dialog_id=obj.id).count()
        return format_html('<a href="{}?dialog__id__exact={}">View Messages ({})</a>', url, obj.id, count)

    view_messages.short_description = 'Messages'


# @admin.register(Instance, site=admin_site)
class InstanceAdmin(admin.ModelAdmin):
    list_display = (
        'username_display', 'codename_display', 'created_at',
        # 'view_dialogs',
        # 'view_messages'
    )
    search_fields = ['username', 'bot__codename']
    list_filter = ['bot__codename', 'created_at']
    readonly_fields = ['created_at']

    # list_editable = ['requests_limit']#, 'default_model']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('bot', 'user').annotate(
            total_cost=models.Sum('dialogs__messages__cost')
        )

    def username_display(self, obj):
        return obj.user.username
    username_display.short_description = 'Username'

    def codename_display(self, obj):
        url = reverse('admin:assistant_bot_bot_change', args=[obj.bot.codename])
        return format_html('<a href="{}">{}</a>', url, obj.bot.codename)
    codename_display.short_description = 'Bot'

    # def view_dialogs(self, obj):
    #     url = reverse('admin:assistant_bot_dialog_changelist')
    #     count = Dialog.objects.filter(instance_id=obj.id).count()
    #     return format_html('<a href="{}?instance__id__exact={}">{}</a>', url, obj.id, count)
    # view_dialogs.short_description = 'Dialogs'

    # def view_messages(self, obj):
    #     url = reverse('admin:assistant_bot_message_changelist')
    #     count = Message.objects.filter(dialog__instance_id=obj.id).count()
    #     return format_html('<a href="{}?dialog__instance__id__exact={}">{}</a>', url, obj.id, count)
    # view_messages.short_description = 'Messages'


# @admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'bot_dialog_display', 'instance_display', 'role', 'text_display',
                    'io_tokens']
    search_fields = ['text', 'role__name']
    list_filter = ['role', 'timestamp', 'dialog__instance__bot__codename', ]
    readonly_fields = ['text_display_detail', 'message_id', 'timestamp', 'dialog', 'role']
    exclude = ['text', 'cost']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('dialog', 'dialog__instance', 'dialog__instance__bot')

    def instance_display(self, obj):
        url = reverse('admin:assistant_bot_instance_change', args=[obj.dialog.instance_id])
        return format_html('<a href="{}">{}</a>', url, obj.dialog.instance.username)

    instance_display.short_description = 'Instance'

    def bot_dialog_display(self, obj):
        bot_url = reverse('admin:assistant_bot_bot_change', args=[obj.dialog.instance.codename])
        dialog_url = reverse('admin:assistant_bot_dialog_change', args=[obj.dialog_id])
        return format_html('<a href="{}">{}</a>&nbsp;(<a href="{}">{}</a>)', bot_url, obj.dialog.instance.bot.codename,
                           dialog_url, obj.dialog_id)

    bot_dialog_display.short_description = 'Bot (Dialog)'

    def text_display(self, obj):
        if obj.text and len(obj.text) > 85:
            return obj.text[:80] + f'... ({len(obj.text)} length)'
        else:
            return obj.text

    text_display.short_description = 'Text'

    def text_display_detail(self, obj):
        if obj.text:
            return obj.text

    text_display_detail.short_description = 'Text'

    def io_tokens(self, obj):
        if obj.cost_details:
            input_tokens = obj.cost_details[-1].get('prompt_tokens', '-')
            output_tokens = obj.cost_details[-1].get('completion_tokens', '-')
            return f"{input_tokens} / {output_tokens}"

    io_tokens.short_description = 'I/O tokens'

    def lookup_allowed(self, lookup, value):
        if lookup in ('dialog__instance__id__exact',):
            return True
        return super().lookup_allowed(lookup, value)
