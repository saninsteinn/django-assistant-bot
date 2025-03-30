# Broadcast Workflow

This document describes the step-by-step process for sending a broadcast through the `assistant.broadcasting` module.

## Phase 1: Preparation and Planning (Administrator)

1.  **Create and Configure Campaign (`BroadcastCampaign`):**
    *   The administrator logs into the Django Admin (`/admin/`).
    *   Navigates to the "Broadcast Campaigns" section.
    *   Creates a new `BroadcastCampaign` record.
    *   Fills in:
        *   `Campaign Name` (optional): Campaign name for the admin interface.
        *   `Bot`: Selects the bot whose users will receive the broadcast.
        *   `Platform`: Selects the platform (defaults to "Telegram").
        *   `Message Text`: Enters the **text** of the message for the broadcast.
        *   `Scheduled At` (optional): Sets the date and time for a delayed start. If not specified, the campaign remains in `DRAFT` status.
    *   Saves the campaign. The status will be `DRAFT` or (potentially) `SCHEDULED`.

## Phase 2: Launching the Sending Process

Two main scenarios:

*   **Option A: Scheduled Sending**
    1.  **Scheduler (Celery Beat):** Periodically runs the `check_scheduled_broadcasts` task.
    2.  **`check_scheduled_broadcasts` (task):** Finds campaigns (`SCHEDULED`, `scheduled_at` <= now), launches `start_campaign_sending_task(campaign_id)` for each.

*   **Option B: Manual Launch (via Admin Action - requires implementation)**
    1.  **Admin Action:** The administrator selects a campaign (`DRAFT`) and applies the "Send Now" action.
    2.  **Action Logic:** Launches `start_campaign_sending_task(campaign_id)`.

## Phase 3: Initiating Sending (Celery Worker)

1.  **`start_campaign_sending_task` (task):**
    *   Calls `services.initiate_campaign_sending(campaign_id)`.

2.  **`services.initiate_campaign_sending` (service):**
    *   Finds the `BroadcastCampaign`.
    *   Checks the status.
    *   **Transaction:**
        *   Locks the campaign, sets `status = SENDING`, `started_at`.
        *   Calls `resolve_target_chat_ids()` -> `chat_ids`.
        *   Records `total_recipients`.
        *   Saves.
    *   If `chat_ids` is empty, calls `finalize_campaign()`.
    *   Determines `bot_codename` and `platform_codename` (now taken from `campaign.platform`).
    *   Forms `message_content_data = {'text': campaign.message_text}`.
    *   Splits `chat_ids` into batches.
    *   For each batch, launches `tasks.send_broadcast_batch.delay(..., platform_codename=campaign.platform, message_content_data=...)`.

## Phase 4: Sending a Batch of Messages (Celery Worker)

1.  **`send_broadcast_batch` (task):**
    *   Calls `_send_broadcast_batch_async`.

2.  **`_send_broadcast_batch_async` (task - async worker):**
    *   Gets the `platform`.
    *   **Deserializes `message_content_data` (`{'text': ...}`)** using `answer_from_dict`.
    *   **Loop over `chat_ids`:**
        *   Calls `_post_notification_helper` -> `platform.post_answer`.
        *   Processes the result (success, `UserUnavailableError`, other error), updates counters, logs, collects `unavailable_user_ids`.
    *   Calls `_mark_users_unavailable` if necessary.
    *   Launches `tasks.record_batch_results_task.delay(...)`.

## Phase 5: Recording Results and Finalization (Celery Worker and Services)

1.  **`record_batch_results_task` (task):** Calls `services.record_batch_results`.
2.  **`services.record_batch_results` (service):** Atomically updates `successful_sents`, `failed_sents` counters. If all are processed, launches `tasks.finalize_campaign_task.delay()`.
3.  **`finalize_campaign_task` (task):** Calls `services.finalize_campaign`.
4.  **`services.finalize_campaign` (service):** Atomically determines and sets the final `status` and `completed_at`.

## Outcome

The `BroadcastCampaign` receives its final status and statistics. The administrator sees the result. Users with `is_unavailable=True` are excluded from subsequent broadcasts.