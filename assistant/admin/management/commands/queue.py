import urllib.parse

from django.conf import settings
from django.core.management.base import BaseCommand
import redis
from assistant.assistant.queue import CeleryQueues


class Command(BaseCommand):
    help = 'Manage Celery queues in Redis'

    def add_arguments(self, parser):
        parser.add_argument('operation', type=str, choices=['list', 'clear', 'remove'], help='Operation to perform on the queue')
        parser.add_argument('--name', type=str, choices=[queue.value for queue in CeleryQueues], help='Name of the queue to manage')
        parser.add_argument('--db', type=int, default=0, help='Redis database number')
        parser.add_argument('--task_id', type=str, help='Task ID to remove (only for remove operation)')

    def handle(self, *args, **kwargs):
        operation = kwargs['operation']

        if kwargs['name']:
            queue_names = [kwargs['name']]
        else:
            queue_names = [queue.value for queue in CeleryQueues]

        db_number = kwargs['db']
        task_id = kwargs.get('task_id')

        # Extract Redis connection details from CELERY_BROKER_URL
        url = urllib.parse.urlparse(settings.CELERY_BROKER_URL)
        redis_host = url.hostname
        redis_port = url.port
        redis_db = int(url.path.lstrip('/'))

        r = redis.Redis(host=redis_host, port=redis_port, db=redis_db)

        if operation == 'list':
            for queue_name in queue_names:
                self.view_queue(r, queue_name)
        elif operation == 'clear':
            for queue_name in queue_names:
                self.clear_queue(r, queue_name)
        elif operation == 'remove':
            if task_id:
                if not kwargs['name']:
                    self.stdout.write(self.style.ERROR('Queue name is required for the remove operation'))
                self.remove_task(r, queue_names[0], task_id)
            else:
                self.stdout.write(self.style.ERROR('Task ID is required for the remove operation'))

    def view_queue(self, r, queue_name):
        queued_tasks = r.lrange(queue_name, 0, -1)
        if queued_tasks:
            for task in queued_tasks:
                self.stdout.write(task.decode('utf-8'))

    def clear_queue(self, r, queue_name):
        r.delete(queue_name)
        self.stdout.write(self.style.SUCCESS(f'Successfully cleared queue `{queue_name}`'))

    def remove_task(self, r, queue_name, task_id):
        queued_tasks = r.lrange(queue_name, 0, -1)
        task_found = False

        for task in queued_tasks:
            if task_id in task.decode('utf-8'):
                r.lrem(queue_name, 1, task)
                task_found = True
                break

        if task_found:
            self.stdout.write(self.style.SUCCESS(f'Successfully removed task {task_id} from queue {queue_name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Task ID {task_id} not found in queue {queue_name}'))
