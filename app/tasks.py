from app.celery_app import celery_app
from app.email_utils import send_email, read_emails_async
import asyncio

@celery_app.task
def send_email_task(subject, recipient, body):
    """
    Синхронная обертка для асинхронной отправки email через Celery.
    """
    return asyncio.run(send_email(subject, recipient, body))

@celery_app.task
def read_emails_task(limit=10):
    """
    Синхронная обертка для асинхронного чтения писем.
    """
    return asyncio.run(read_emails_async(limit))
