from enum import Enum


class CeleryQueues(Enum):
    QUERY = 'query'
    PROCESSING = 'processing'
