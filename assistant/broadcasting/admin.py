from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import BroadcastCampaign


class BroadcastCampaignAdmin(admin.ModelAdmin):
    list_display = (
        '__str__',
        'bot',
        'platform',
        'message_text',
        'status',
        'scheduled_at',
        'total_recipients',
        'successful_sents',
        'failed_sents',
        'created_at',
    )
    list_filter = ('status', 'platform', 'bot', 'scheduled_at', 'created_at')
    search_fields = ('name', 'bot__name', 'message_text')
    readonly_fields = (
        'status',
        'started_at',
        'completed_at',
        'total_recipients',
        'successful_sents',
        'failed_sents',
        'created_at',
        'updated_at'
    )
    fieldsets = (
        (None, {
            'fields': ('name', 'bot', 'platform', 'message_text', 'scheduled_at')
        }),
        (_('Status & Statistics'), {
            'classes': ('collapse',),
            'fields': (
                'status',
                'started_at',
                'completed_at',
                'total_recipients',
                'successful_sents',
                'failed_sents',
            ),
        }),
        (_('Timestamps'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.status == BroadcastCampaign.Status.DRAFT:
            if 'scheduled_at' in readonly: readonly.remove('scheduled_at')
            if 'message_text' in readonly: readonly.remove('message_text')
            if 'platform' in readonly: readonly.remove('platform')
        elif obj:
            if 'scheduled_at' not in readonly: readonly.append('scheduled_at')
            if 'message_text' not in readonly: readonly.append('message_text')
            if 'platform' not in readonly: readonly.append('platform')

        if obj and obj.status != BroadcastCampaign.Status.DRAFT:
            if 'name' not in readonly: readonly.append('name')
            if 'bot' not in readonly: readonly.append('bot')
            if 'platform' not in readonly: readonly.append('platform')

        return tuple(readonly)

    # TODO: Add custom admin actions like "Send Now", "Cancel Scheduled Campaign"