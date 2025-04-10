from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import BroadcastCampaign

@receiver(pre_save, sender=BroadcastCampaign)
def update_campaign_status_on_schedule(sender, instance, **kwargs):
    """
    Updates the campaign status based on the scheduled_at field before saving.
    - If scheduled_at is set and status is DRAFT, change status to SCHEDULED.
    - If scheduled_at is cleared and status is SCHEDULED, change status back to DRAFT.
    """
    # Avoid infinite loops during status updates triggered by other parts of the system,
    # e.g., when tasks update only the status or statistics.
    # If 'update_fields' is present and only contains 'status' or stats fields, skip.
    update_fields = kwargs.get('update_fields', None)
    if update_fields and all(field in {'status', 'started_at', 'completed_at', 'total_recipients', 'successful_sents', 'failed_sents'} for field in update_fields):
        return

    # Check if the object is being created or already exists
    try:
        # Fetch the previous state from the database only if the instance has a pk
        if instance.pk:
            original_instance = sender.objects.get(pk=instance.pk)
            original_status = original_instance.status
        else:
            # This is a new instance being created
            original_status = BroadcastCampaign.Status.DRAFT # Explicitly set default for comparison logic
    except sender.DoesNotExist:
        # Should not happen in pre_save if pk exists, but handle defensively
        original_status = BroadcastCampaign.Status.DRAFT # Fallback for safety

    # Case 1: Schedule a Draft campaign
    if instance.scheduled_at and instance.status == BroadcastCampaign.Status.DRAFT:
        instance.status = BroadcastCampaign.Status.SCHEDULED
        print(f"Campaign {instance.pk}: Status changed from DRAFT to SCHEDULED (scheduled_at set)")

    # Case 2: Unschedule a Scheduled campaign (revert to Draft)
    # Check the *current* instance status is SCHEDULED before reverting
    elif instance.scheduled_at is None and instance.status == BroadcastCampaign.Status.SCHEDULED:
         # Also check the *original* status to prevent reverting if it was already sending/completed etc.
         # This ensures we only revert DRAFT <-> SCHEDULED transitions triggered by scheduled_at changes.
        if original_status == BroadcastCampaign.Status.SCHEDULED:
            instance.status = BroadcastCampaign.Status.DRAFT
            print(f"Campaign {instance.pk}: Status changed from SCHEDULED to DRAFT (scheduled_at cleared)")
        # Optional: Add logging if status is SCHEDULED but original wasn't, indicating an unexpected state?
        # else:
        #     print(f"Campaign {instance.pk}: scheduled_at cleared, but status is SCHEDULED and original was {original_status}. No status change.")

    # Optional: Log other transitions or unchanged status for debugging
    # elif instance.status != original_status:
    #      print(f"Campaign {instance.pk}: Status changed from {original_status} to {instance.status} (not schedule-related)")
    # else:
    #      print(f"Campaign {instance.pk}: Status {instance.status} unchanged during save.")