from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enterprise", "0244_enable_academies_for_existing_customers"),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomer',
            name='enable_academies',
            field=models.BooleanField(
                default=True,
                help_text='If checked, the learners will be able to see the academies on the learner portal dashboard.',
                verbose_name='Display academies screen',
            ),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomer',
            name='enable_academies',
            field=models.BooleanField(
                default=True,
                help_text='If checked, the learners will be able to see the academies on the learner portal dashboard.',
                verbose_name='Display academies screen',
            ),
        ),
    ]
