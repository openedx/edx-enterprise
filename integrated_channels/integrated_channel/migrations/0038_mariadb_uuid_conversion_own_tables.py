"""
Convert this app's UUIDField columns from char(32) to uuid on MariaDB.

0037_mariadb_uuid_conversion was released altering the channel_integration_*
tables, the enterprise-integrated-channels copies of this app's tables, which
that package converts in its own migrations. Those tables have no ordering
guarantee against 0037, and this app's own columns kept char(32). 0037 now
names this app's tables; this migration converts them on databases that
applied the old version. MODIFY to the type a column already has changes
nothing, so it is also safe after the corrected 0037.

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
        cursor.execute("ALTER TABLE integrated_channel_genericlearnerdatatransmissionaudit MODIFY enterprise_customer_uuid uuid NULL")
        cursor.execute("ALTER TABLE integrated_channel_contentmetadataitemtransmission MODIFY enterprise_customer_catalog_uuid uuid NULL")


class Migration(migrations.Migration):

    dependencies = [
        ('integrated_channel', '0037_mariadb_uuid_conversion'),
    ]

    operations = [
        # Reversing to char(32) is left to 0037_mariadb_uuid_conversion, which this repeats.
        migrations.RunPython(
            code=apply_mariadb_migration,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
