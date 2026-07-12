import pymysql
pymysql.install_as_MySQLdb()

# Load the Celery app when Django starts so @shared_task is available everywhere.
from .celery import app as celery_app  # noqa: F401

__all__ = ('celery_app',)
