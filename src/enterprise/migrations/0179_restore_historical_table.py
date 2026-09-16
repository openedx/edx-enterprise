from django.db import connection, migrations


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0178_auto_20230808_0923'),
    ]

    # At one point we ran into migration deployment issues that caused us to manually change and alter tables on stage
    # and prod. One unintended consequence of this event was that the historical licensed enrollment table was dropped
    # and never restored on __stage__ only. This migration restores the historical licensed enrollment table IFF it
    # does not exist as to bypass the error that would occur if we tried to create a table that already exists.
    # Relevant RCA: https://2u-internal.atlassian.net/wiki/spaces/ENG/pages/345374826/RCA+Enterprise+partially-applied+licensed+course+enrollment+migration
    db_engine = connection.settings_dict['ENGINE']
    if 'mysql' in db_engine:
        operations = [
            migrations.RunSQL(
                """
                CREATE TABLE IF NOT EXISTS `enterprise_historicallicensedenterprisecourseenrollment` (
                `id` int(11) NOT NULL,
                `created` datetime(6) NOT NULL,
                `modified` datetime(6) NOT NULL,
                `license_uuid` char(32) NOT NULL,
                `history_id` int(11) NOT NULL AUTO_INCREMENT,
                `history_date` datetime(6) NOT NULL,
                `history_change_reason` varchar(100) DEFAULT NULL,
                `history_type` varchar(1) NOT NULL,
                `enterprise_course_enrollment_id` int(11) DEFAULT NULL,
                `history_user_id` int(11) DEFAULT NULL,
                `is_revoked` tinyint(1) NOT NULL,
                PRIMARY KEY (`history_id`),
                KEY `enterprise_historica_history_user_id_1db87766_fk_auth_user` (`history_user_id`),
                KEY `enterprise_historicallicens_id_ff4cfd4f` (`id`),
                KEY `enterprise_historicallicens_enterprise_course_enrollmen_1b0d3427` (`enterprise_course_enrollment_id`),
                CONSTRAINT `enterprise_historica_history_user_id_1db87766_fk_auth_user` FOREIGN KEY (`history_user_id`) REFERENCES `auth_user` (`id`)
                );
                """,
                reverse_sql=migrations.RunSQL.noop,
            ),
        ]
