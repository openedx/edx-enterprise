"""
Convert blackboard_blackboardenterprisecustomerconfiguration.uuid from char(32) to uuid on MariaDB.

0025_mariadb_uuid_conversion was released altering
blackboard_channel_blackboardenterprisecustomerconfiguration, the
enterprise-integrated-channels copy of this table, which that package converts
in its own migrations. On a fresh database 0025 failed because nothing creates
that table first, and on existing databases this table kept its char(32)
column. 0025 now names this table; this migration converts it on databases that
applied the old version. MODIFY to the type a column already has changes
nothing, so it is also safe after the corrected 0025.

See: https://docs.djangoproject.com/en/5.2/releases/5.0/#migrating-uuidfield
"""

from django.db import migrations


def _is_mariadb(connection):
    if connection.vendor != 'mysql':
        return False
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        return 'mariadb' in cursor.fetchone()[0].lower()


def apply_mariadb_migration(apps, schema_editor):
    if not _is_mariadb(schema_editor.connection):
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("ALTER TABLE blackboard_blackboardenterprisecustomerconfiguration MODIFY uuid uuid NOT NULL")


class Migration(migrations.Migration):

    dependencies = [
        ('blackboard', '0025_mariadb_uuid_conversion'),
    ]

    operations = [
        # Reversing to char(32) is left to 0025_mariadb_uuid_conversion, which this repeats.
        migrations.RunPython(
            code=apply_mariadb_migration,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
