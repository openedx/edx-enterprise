# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sap_success_factors', '0009_sapsuccessfactors_remove_enterprise_enrollment_page_waffle_flag'),
    ]

    database_operations = [
        # We just move this table to the "integrated_channel" app, so rename it to prefix it with "integrated_channel".
        migrations.AlterModelTable('CatalogTransmissionAudit', 'integrated_channel_catalogtransmissionaudit'),
    ]

    state_operations = [
        # See `integrated_channel.migrations.0003` for the migration that adds this model to the other app's state.
        migrations.DeleteModel(name='CatalogTransmissionAudit')
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=database_operations,
            state_operations=state_operations
        ),
        migrations.RenameModel('LearnerDataTransmissionAudit', 'SapSuccessFactorsLearnerDataTransmissionAudit')
    ]
