from django.db import connection, migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('blackboard', '0012_move_and_recrete_completed_timestamp'),
    ]

    db_engine = connection.settings_dict['ENGINE']

    if 'postgresql' in db_engine:
        operations = [
            migrations.SeparateDatabaseAndState(
                state_operations=[
                    migrations.AlterIndexTogether(
                        name='blackboardlearnerdatatransmissionaudit',
                        index_together={('enterprise_customer_uuid', 'plugin_configuration_id')},
                    ),
                ],
                database_operations=[
                    migrations.RunSQL(sql="""
                                          CREATE INDEX CONCURRENTLY blackboard_bldta_85936b55_idx
                                              ON blackboard_blackboardlearnerdatatransmissionaudit (enterprise_customer_uuid, plugin_configuration_id)
                                          """, reverse_sql="""
                                                           DROP INDEX CONCURRENTLY blackboard_bldta_85936b55_idx
                                                           """),
                ]
            ),
        ]
    elif 'mysql' in db_engine:
        # For MySQL or other non-sqlite and non-postgresql backends
        operations = [
            migrations.SeparateDatabaseAndState(
                state_operations=[
                    migrations.AlterIndexTogether(
                        name='blackboardlearnerdatatransmissionaudit',
                        index_together={('enterprise_customer_uuid', 'plugin_configuration_id')},
                    ),
                ],
                database_operations=[
                    migrations.RunSQL(sql="""
                                          CREATE INDEX blackboard_bldta_85936b55_idx
                                              ON blackboard_blackboardlearnerdatatransmissionaudit (enterprise_customer_uuid, plugin_configuration_id)
                                              ALGORITHM = INPLACE LOCK = NONE
                                          """, reverse_sql="""
                                                           DROP INDEX blackboard_bldta_85936b55_idx
                                                               ON blackboard_blackboardlearnerdatatransmissionaudit
                                                           """),
                ]
            ),
        ]
    else:
        operations = [
            migrations.AlterIndexTogether(
                name='blackboardlearnerdatatransmissionaudit',
                index_together={('enterprise_customer_uuid', 'plugin_configuration_id')},
            ),
        ]
