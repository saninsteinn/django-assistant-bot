from django.db import models
from django.utils.translation import gettext_lazy as _

# Assuming assistant.bot.models exists and contains Bot
# Adjust the import path if necessary based on your project structure
from assistant.bot.models import Bot


class BroadcastCampaign(models.Model):
    """
    Represents a specific broadcast event, linking content, targeting, scheduling, and status.
    Message content is now directly included.
    """
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', _('Draft')
        SCHEDULED = 'SCHEDULED', _('Scheduled')
        SENDING = 'SENDING', _('Sending')
        COMPLETED = 'COMPLETED', _('Completed')
        PARTIAL_FAILURE = 'PARTIAL_FAILURE', _('Partial Failure') # Some sends failed, but not all
        FAILED = 'FAILED', _('Failed') # Major failure during initiation or all sends failed
        CANCELED = 'CANCELED', _('Canceled')

    # Add PlatformChoices enum
    class PlatformChoices(models.TextChoices):
        TELEGRAM = 'telegram', _('Telegram')
        # Add other platforms here in the future if needed
        # WHATSAPP = 'whatsapp', _('WhatsApp')

    name = models.CharField(
        _("Campaign Name"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("Optional name for easy identification in the admin interface.")
    )
    # Add simple text field for the message
    message_text = models.TextField(
        _("Message Text"),
        help_text=_("The text content of the broadcast message.")
    )
    bot = models.ForeignKey(
        Bot,
        on_delete=models.CASCADE,
        related_name='broadcast_campaigns',
        verbose_name=_("Bot")
    )
    # Add platform field
    platform = models.CharField(
        _("Platform"),
        max_length=20,
        choices=PlatformChoices.choices,
        default=PlatformChoices.TELEGRAM,
        help_text=_("The messaging platform for this campaign.")
    )
    # TODO: Implement more sophisticated targeting later.
    # target_criteria = models.JSONField(...)
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True
    )
    scheduled_at = models.DateTimeField(
        _("Scheduled At"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_("If set, the campaign will start sending at this time. If blank, it can be sent manually.")
    )
    started_at = models.DateTimeField(_("Started Sending At"), null=True, blank=True)
    completed_at = models.DateTimeField(_("Completed At"), null=True, blank=True)

    # Statistics - updated by tasks
    total_recipients = models.PositiveIntegerField(
        _("Total Recipients"),
        null=True,
        blank=True,
        help_text=_("Estimated or actual number of unique recipients targeted.")
    )
    successful_sents = models.PositiveIntegerField(_("Successful Sends"), default=0)
    failed_sents = models.PositiveIntegerField(
        _("Failed Sends"),
        default=0,
        help_text=_("Includes users marked as unavailable and other delivery errors.")
    )

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    def __str__(self):
        # Update __str__ to maybe include platform?
        return self.name or f"Campaign for {self.bot.codename} on {self.get_platform_display()} ({self.get_status_display()})"

    class Meta:
        verbose_name = _("Broadcast Campaign")
        verbose_name_plural = _("Broadcast Campaigns")
        ordering = ['-scheduled_at', '-created_at']