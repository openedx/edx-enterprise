# Generated migration for MariaDB UUID field conversion (Django 5.2)
"""
Migration to convert UUIDField from char(32) to uuid type for MariaDB compatibility.

See: https://www.albertyw.com/note/django-5-mariadb-uuidfield
"""

from django.db import migrations


def apply_mariadb_migration(apps, schema_editor):
    connection = schema_editor.connection

    if connection.vendor != 'mysql':
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        if 'mariadb' not in version.lower():
            return

    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE canvas_channel_canvasenterprisecustomerconfiguration MODIFY uuid uuid NOT NULL")


def reverse_mariadb_migration(apps, schema_editor):
    connection = schema_editor.connection

    if connection.vendor != 'mysql':
        return

    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()[0]
        if 'mariadb' not in version.lower():
            return

    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE canvas_channel_canvasenterprisecustomerconfiguration MODIFY uuid char(32) NOT NULL")


class Migration(migrations.Migration):

    dependencies = [
        ('canvas', '0040_rename_canvaslearnerdatatransmissionaudit_enterprise_customer_uuid_plugin_configuration_id_canvas_cu'),
    ]

    operations = [
        migrations.RunPython(
            code=apply_mariadb_migration,
            reverse_code=reverse_mariadb_migration,
        ),
    ]
