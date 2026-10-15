from django.db import connection, migrations


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ('integrated_channel', '0027_orphanedcontenttransmissions'),
    ]

    db_engine = connection.settings_dict['ENGINE']

    if 'postgresql' in db_engine:
        operations = [
            migrations.SeparateDatabaseAndState(
                state_operations=[
                    migrations.AlterUniqueTogether(
                        name='contentmetadataitemtransmission',
                        unique_together={('integrated_channel_code', 'plugin_configuration_id', 'content_id')},
                    ),
                ],
                database_operations=[
                    migrations.RunSQL(
                        sql="""
                            CREATE UNIQUE INDEX CONCURRENTLY content_transmission_channel_code_plugin_id_content_id_unique
                                ON integrated_channel_contentmetadataitemtransmission (integrated_channel_code, plugin_configuration_id, content_id)
                            """,
                        reverse_sql="""
                                    DROP INDEX CONCURRENTLY content_transmission_channel_code_plugin_id_content_id_unique
                                    """
                    ),
                ],
            ),
        ]
    elif 'mysql' in db_engine:
        # For MySQL or other non-sqlite and non-postgresql backends
        operations = [
            migrations.SeparateDatabaseAndState(
                state_operations=[
                    migrations.AlterUniqueTogether(
                        name='contentmetadataitemtransmission',
                        unique_together={('integrated_channel_code', 'plugin_configuration_id', 'content_id')},
                    ),
                ],
                database_operations=[
                    migrations.RunSQL(
                        sql="""
                            CREATE UNIQUE INDEX content_transmission_channel_code_plugin_id_content_id_unique
                                ON integrated_channel_contentmetadataitemtransmission (integrated_channel_code, plugin_configuration_id, content_id)
                                ALGORITHM = INPLACE LOCK = NONE
                            """,
                        reverse_sql="""
                                    DROP INDEX content_transmission_channel_code_plugin_id_content_id_unique
                                        ON integrated_channel_contentmetadataitemtransmission
                                    """
                    ),
                ],
            ),
        ]
    else:
        operations = [
            migrations.AlterUniqueTogether(
                name='contentmetadataitemtransmission',
                unique_together={('integrated_channel_code', 'plugin_configuration_id', 'content_id')},
            ),
        ]
