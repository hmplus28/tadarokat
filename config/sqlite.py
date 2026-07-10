"""تنظیمات SQLite برای جلوگیری از database is locked"""
from django.db.backends.signals import connection_created


def configure_sqlite_connection(sender, connection, **kwargs):
    if connection.vendor != 'sqlite':
        return
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA busy_timeout=30000;')
        cursor.execute('PRAGMA foreign_keys=ON;')


def setup_sqlite_pragmas():
    connection_created.connect(configure_sqlite_connection)