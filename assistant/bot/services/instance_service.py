from contextlib import AbstractAsyncContextManager
import logging

from asgiref.sync import sync_to_async
from django_pglocks import advisory_lock

logger = logging.getLogger(__name__)

import logging
from contextlib import AbstractAsyncContextManager

logger = logging.getLogger(__name__)


class BaseInstanceLock:
    def __init__(self, instance):
        self.instance = instance
        self.lock_key = hash(self.instance.id) & 0xFFFFFFFF
        self._instance_lock = None

    def _get_lock(self):
        self._instance_lock = advisory_lock(self.lock_key)

    def _log_acquire(self):
        logger.debug('Acquiring instance lock...')

    def _log_acquired(self):
        logger.debug('Instance lock acquired')

    def _log_release(self):
        logger.debug('Releasing instance lock...')

    def _log_released(self):
        logger.debug('Instance lock released')


class InstanceLock(BaseInstanceLock):
    def __enter__(self):
        self._log_acquire()
        self._get_lock()
        self._instance_lock.__enter__()
        self._log_acquired()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._log_release()
        if self._instance_lock:
            self._instance_lock.__exit__(exc_type, exc_val, exc_tb)
        self._log_released()


class InstanceLockAsync(BaseInstanceLock, AbstractAsyncContextManager):
    async def __aenter__(self):
        self._log_acquire()
        self._get_lock()
        await sync_to_async(self._instance_lock.__enter__)()
        self._log_acquired()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._log_release()
        if self._instance_lock:
            await sync_to_async(self._instance_lock.__exit__)(exc_type, exc_val, exc_tb)
        self._log_released()

