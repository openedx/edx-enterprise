from django.db import migrations, models

def enable_credit_and_industry_pathways_for_existing_customers(apps, schema_editor):
    """
    Backfill existing enterprise customers to match the new default.
    """
    EnterpriseCustomer = apps.get_model("enterprise", "EnterpriseCustomer")
    EnterpriseCustomer.objects.filter(
        enable_credit_and_industry_pathways=False,
    ).update(
        enable_credit_and_industry_pathways=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('enterprise', '0247_enterprisecustomer_enable_credit_and_industry_pathways_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='enterprisecustomer',
            name='enable_credit_and_industry_pathways',
            field=models.BooleanField(default=True, help_text='Controls the visibility of Credit and Industry Pathways in the learner portal.', verbose_name='Display credit and industry pathways'),
        ),
        migrations.AlterField(
            model_name='historicalenterprisecustomer',
            name='enable_credit_and_industry_pathways',
            field=models.BooleanField(default=True, help_text='Controls the visibility of Credit and Industry Pathways in the learner portal.', verbose_name='Display credit and industry pathways'),
        ),
        # Reverse is a no-op because the original values are not knowable.
        migrations.RunPython(
            enable_credit_and_industry_pathways_for_existing_customers,
            migrations.RunPython.noop,
        ),
    ]
