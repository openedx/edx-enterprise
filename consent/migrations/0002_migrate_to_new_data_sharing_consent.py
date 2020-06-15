# -*- coding: utf-8 -*-
"""
Custom migration to transfer consent data from the ``enterprise`` application to the ``consent`` application's
``DataSharingConsent`` model.

This migration only does anything significant when running forward. If you would like to do a backwards-migration,
delete all new rows that were populated in the ``DataSharingConsent`` model's tables.
(If you have new data in the tables that weren't migrated, use timestamps as you see fit).

The reason there's no backwards-migration in code is because we can't reasonably determine which
data was transferred and which data is new at the time of the migration. In order to avoid deleting
new data, we simply leave it to someone with DB access to manage things based on the desired timestamp.
"""

from django.db import migrations


def populate_data_sharing_consent(apps, schema_editor):
    """
    Populates the ``DataSharingConsent`` model with the ``enterprise`` application's consent data.

    Consent data from the ``enterprise`` application come from the ``EnterpriseCourseEnrollment`` model.
    """
    DataSharingConsent = apps.get_model('consent', 'DataSharingConsent')
    EnterpriseCourseEnrollment = apps.get_model('enterprise', 'EnterpriseCourseEnrollment')
    User = apps.get_model('auth', 'User')
    for enrollment in EnterpriseCourseEnrollment.objects.all():
        user = User.objects.get(pk=enrollment.enterprise_customer_user.user_id)
        data_sharing_consent, __ = DataSharingConsent.objects.get_or_create(
            username=user.username,
            enterprise_customer=enrollment.enterprise_customer_user.enterprise_customer,
            course_id=enrollment.course_id,
        )
        if enrollment.consent_granted is not None:
            data_sharing_consent.granted = enrollment.consent_granted
        else:
            # Check UDSCA instead.
            consent_state = enrollment.enterprise_customer_user.data_sharing_consent.first()
            if consent_state is not None:
                data_sharing_consent.granted = consent_state.state in ['enabled', 'external']
            else:
                data_sharing_consent.granted = False
        data_sharing_consent.save()


class Migration(migrations.Migration):

    dependencies = [
        # Make sure enterprise models (source) are available.
        ('enterprise', '0024_enterprisecustomercatalog_historicalenterprisecustomercatalog'),
        # Make sure consent models (target) are available.
        ('consent', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            populate_data_sharing_consent,
            reverse_code=lambda apps, schema_editor: None
        ),
    ]
