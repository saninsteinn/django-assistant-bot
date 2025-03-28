# Example of using Django Assistant Bot

This is a Django project.

## Prerequisites

* create `.env` and fill it
* run Django server
* optionally: run `celery -A example worker -Q query` to start the Celery worker to process messages from Telegram


## Useful commands

```bash
# Run bot in interactive mode in console
./manage.py chat task_manager

# Run Telegram bot in long polling mode (using Celery)
./manage.py telegram_poll task_manager

# Run Telegram bot in synchronous mode (without Celery)
./manage.py telegram_poll task_manager --sync
```

> **Note**: The `telegram_poll` command now uses a direct mechanism for receiving updates from Telegram API instead of the python-telegram-bot library.