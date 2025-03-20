from django.conf import settings
from django.db import migrations, models, connection
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('enterprise', '0230_alter_enterprisecustomeruser_user_fk_and_more'),
    ]

    db_engine = connection.settings_dict['ENGINE']
    if 'sqlite3' in db_engine:
        operations = []
    else:
        operations = [
            migrations.RunSQL(
                sql="""
                    SET FOREIGN_KEY_CHECKS = 0;

                    ALTER TABLE enterprise_enterprisecustomeruser
                    ADD CONSTRAINT fk_enterprisecustomeruser_user_fk
                    FOREIGN KEY (user_fk) REFERENCES auth_user(id)
                    ON DELETE CASCADE,
                    ALGORITHM=INPLACE,
                    LOCK=NONE;

                    ALTER TABLE enterprise_historicalenterprisecustomeruser
                    ADD CONSTRAINT fk_historical_enterprisecustomeruser_user_fk
                    FOREIGN KEY (user_fk) REFERENCES auth_user(id)
                    ON DELETE CASCADE,
                    ALGORITHM=INPLACE,
                    LOCK=NONE;

                    SET FOREIGN_KEY_CHECKS = 1;
                """,
                reverse_sql="""
                    ALTER TABLE enterprise_historicalenterprisecustomeruser
                    DROP FOREIGN KEY fk_historical_enterprisecustomeruser_user_fk;

                    ALTER TABLE enterprise_enterprisecustomeruser
                    DROP FOREIGN KEY fk_enterprisecustomeruser_user_fk;
                """,
                state_operations=[
                    migrations.AlterField(
                        model_name='enterprisecustomeruser',
                        name='user_fk',
                        field=models.ForeignKey(
                            null=True,
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='enterprise_customer_users',
                            to=settings.AUTH_USER_MODEL,
                        ),
                    ),
                    migrations.AlterField(
                        model_name='historicalenterprisecustomeruser',
                        name='user_fk',
                        field=models.ForeignKey(
                            null=True,
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='+',  # Historical tables often use '+' for no backward relation
                            to=settings.AUTH_USER_MODEL,
                        ),
                    ),
                ],
            ),
        ]
