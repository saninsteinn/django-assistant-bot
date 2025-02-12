# Example of using Django Assistant Bot

This is a Django project.

## Prerequisites

* create `.env` and fill it
* run Django server
* create a `Bot` instance in the Django admin panel with codename `task_manager`
* run `celery -A example worker -Q query` to start the Celery worker to process messages from Telegram


## Useful commands

```bash
./manage.py chat task_manager
```