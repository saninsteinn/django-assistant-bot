from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

import json
import logging
from asgiref.sync import async_to_sync
from assistant.bot.models import Bot, BotUser, Instance
from assistant.bot.utils import get_bot_platform
from assistant.bot.domain import answer_from_dict
from .tasks import _post_notification_helper
from assistant.bot.exceptions import UserUnavailableError

from .models import BroadcastCampaign

# Get logger instance
logger = logging.getLogger(__name__)

class BroadcastCampaignAdmin(admin.ModelAdmin):
    list_display = (
        '__str__',
        'bot',
        'platform',
        # 'message_text',
        'status',
        'total_recipients',
        'successful_sents',
        'failed_sents',
        'created_at',
    )
    list_filter = ('status', 'platform', 'bot', 'created_at')
    search_fields = ('name', 'bot__name', 'message_text')
    readonly_fields = (
        'status',
        'started_at',
        'completed_at',
        'total_recipients',
        'successful_sents',
        'failed_sents',
        'created_at',
        'updated_at',
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

    def get_changeform_initial_data(self, request):
        """
        Sets initial data for the change form (add view).
        Prefills the 'bot' field if only one Bot exists.
        """
        initial = super().get_changeform_initial_data(request)
        bots = Bot.objects.all()
        if bots.count() == 1:
            initial['bot'] = bots.first().pk
        return initial

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

    # --- Custom Button Logic Start ---

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:campaign_id>/send-test/',
                self.admin_site.admin_view(self.process_send_test),
                name='broadcasting_broadcastcampaign_send_test'
            ),
            path(
                'ajax-send-test/',
                self.admin_site.admin_view(self.ajax_send_test_message),
                name='broadcasting_broadcastcampaign_ajax_send_test'
            ),
        ]
        return custom_urls + urls

    def process_send_test(self, request: HttpRequest, campaign_id: int):
        """View to process the test send request."""
        campaign = self.get_object(request, campaign_id)

        if not campaign:
            messages.error(request, "Campaign not found.")
            return HttpResponseRedirect(reverse('admin:broadcasting_broadcastcampaign_changelist'))

        if campaign.status != BroadcastCampaign.Status.DRAFT:
            messages.warning(request, "Test messages can only be sent for campaigns in DRAFT status.")
            return HttpResponseRedirect(reverse('admin:broadcasting_broadcastcampaign_change', args=[campaign.pk]))

        if request.method != 'POST':
            messages.error(request, "Invalid request method.")
            return HttpResponseRedirect(reverse('admin:broadcasting_broadcastcampaign_change', args=[campaign.pk]))

        test_username = request.POST.get('test_username')
        if not test_username:
            messages.error(request, "Test username cannot be empty.")
            return HttpResponseRedirect(reverse('admin:broadcasting_broadcastcampaign_change', args=[campaign.pk]))

        # Prepend @ if missing
        if not test_username.startswith('@'):
            test_username = '@' + test_username

        try:
            # 1. Get BotUser and chat_id
            # Assuming username is unique per platform for the bot context
            bot_user = BotUser.objects.get(platform=campaign.platform, username=test_username)
            chat_id = bot_user.user_id

            # 2. Get Platform Instance
            platform_instance = get_bot_platform(campaign.bot.codename, campaign.platform)

            # 3. Deserialize Message Content
            message_data = json.loads(campaign.message_text)
            message_content = answer_from_dict(message_data)

            # 4. Send the message using the helper (sync wrapper)
            # We need to wrap the async helper call
            send_func = async_to_sync(_post_notification_helper)
            send_func(platform_instance, chat_id, message_content)

            messages.success(request, f"Test message successfully sent to {test_username}.")

        except BotUser.DoesNotExist:
            messages.error(request, f"User with username '{test_username}' not found for platform '{campaign.platform}'.")
        except UserUnavailableError:
            messages.warning(request, f"User '{test_username}' is currently unavailable or has blocked the bot.")
        except json.JSONDecodeError:
            messages.error(request, "Failed to parse message content. Ensure it's valid JSON.")
        except Exception as e:
            logger.error(f"Error sending test message for campaign {campaign_id} to {test_username}: {e}", exc_info=True)
            messages.error(request, f"An unexpected error occurred: {e}")

        # Redirect back to the change form
        return HttpResponseRedirect(reverse('admin:broadcasting_broadcastcampaign_change', args=[campaign.pk]))

    @method_decorator(csrf_protect)
    def ajax_send_test_message(self, request: HttpRequest):
        """Handles AJAX request to send a test message from the add form."""
        if not request.method == 'POST':
            return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)

        try:
            data = json.loads(request.body)
            bot_id = data.get('bot_id')
            platform_code = data.get('platform_code')
            message_text = data.get('message_text')
            test_username = data.get('test_username')

            if not all([bot_id, platform_code, message_text, test_username]):
                return JsonResponse({'status': 'error', 'message': 'Missing required data.'}, status=400)

            # Prepend @ if missing
            if not test_username.startswith('@'):
                test_username = '@' + test_username

            # Convert bot_id to int
            try:
                bot_id = int(bot_id)
            except (ValueError, TypeError):
                 return JsonResponse({'status': 'error', 'message': 'Invalid Bot ID.'}, status=400)

            # --- Logic similar to process_send_test but using provided data ---
            # 1. Get Bot codename
            bot = get_object_or_404(Bot, pk=bot_id)
            bot_codename = bot.codename

            # 2. Get BotUser and chat_id
            bot_user = BotUser.objects.get(platform=platform_code, username=test_username)
            chat_id = bot_user.user_id

            # 3. Get Platform Instance
            platform_instance = get_bot_platform(bot_codename, platform_code)

            # 4. Deserialize Message Content
            # Corrected: Wrap the raw text in the expected dict structure
            # message_data_dict = json.loads(message_text)
            message_data_dict = {'text': message_text}
            message_content = answer_from_dict(message_data_dict)

            # 5. Send the message using the helper
            send_func = async_to_sync(_post_notification_helper)
            send_func(platform_instance, chat_id, message_content)

            # Use the potentially modified test_username in the success message
            return JsonResponse({'status': 'success', 'message': f"Test message successfully sent to {test_username}."})

        except Bot.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Selected Bot not found.'}, status=404)
        except BotUser.DoesNotExist:
            # Use the potentially modified test_username in the error message
            return JsonResponse({'status': 'error', 'message': f"User '{test_username}' not found for platform '{platform_code}'."}, status=404)
        except UserUnavailableError:
            # Use the potentially modified test_username in the warning message
            return JsonResponse({'status': 'warning', 'message': f"User '{test_username}' is currently unavailable or has blocked the bot."}, status=400)
        # Remove the broad JSONDecodeError catch, as we no longer parse message_text as JSON here.
        # Keep the one for request.body if needed, though it might be less likely now.
        # except json.JSONDecodeError as e:
        #    ...
        except Exception as e:
            # Specifically check if the error comes from answer_from_dict
            if isinstance(e, TypeError) and 'answer_from_dict()' in str(e):
                logger.error(f"Error creating answer object from dict: {e}. Dict was: {message_data_dict}", exc_info=True)
                return JsonResponse({'status': 'error', 'message': 'Internal error creating message object.'}, status=500)

            logger.error(f"Error sending AJAX test message: {e}", exc_info=True)
            return JsonResponse({'status': 'error', 'message': f"An unexpected error occurred: {e}"}, status=500)

    # Template settings remain as they might still be needed if other customizations exist
    change_form_template = "admin/broadcasting/broadcastcampaign/change_form.html"
    add_form_template = "admin/broadcasting/broadcastcampaign/add_form.html"

    # Modify the change view context to include button rendering data
    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        campaign = self.get_object(request, object_id)

        if campaign and campaign.status == BroadcastCampaign.Status.DRAFT:
            # Test Send Button Context
            test_send_url = reverse('admin:broadcasting_broadcastcampaign_send_test', args=[campaign.pk])
            extra_context['show_test_send'] = True
            extra_context['test_send_url'] = test_send_url

        return super().change_view(
            request, object_id, form_url, extra_context=extra_context,
        )

    # TODO: Add custom admin actions like "Send Now", "Cancel Scheduled Campaign"
    # TODO: Add logic for scheduling button/action