import os
from celery import Celery

from urllib.parse import quote_plus


endpoint_url = 'sqs://{}:{}@'.format(
    quote_plus(os.environ.get('AWS_ACCESS_KEY_ID')),
    quote_plus(os.environ.get('AWS_SECRET_ACCCESS_KEY'))
)

# CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379'),
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', endpoint_url),
# CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://redis-prod:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')


celery = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
