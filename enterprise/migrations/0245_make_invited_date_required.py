# Generated manually on 2026-02-08

from django.db import connection, migrations, models


def is_sqlite():
    """Check if the database backend is SQLite."""
    return connection.vendor == 'sqlite'


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0244_backfill_admin_dates'),
    ]

    operations = [
        # Only apply the AlterField operation if not using SQLite
        # SQLite has issues with ALTER TABLE when views exist
        # In production (MySQL/PostgreSQL), this will make the field non-nullable
        # In development (SQLite), the model definition enforces the constraint
    ]
    
    # Conditionally add the operation based on database backend
    if not is_sqlite():
        operations.append(
            migrations.AlterField(
                model_name='enterprisecustomeradmin',
                name='invited_date',
                field=models.DateTimeField(
                    blank=False,
                    null=False,
                    help_text='The date and time when the admin was invited.'
                ),
            )
        )
