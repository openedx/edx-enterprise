"""
Utilities for SAP Success Factors integrated channel.
"""


def populate_decrypted_fields_sap_success_factors(apps, schema_editor=None):  # pylint: disable=unused-argument
    """
    Populates the encryption fields in SAP Success Factors config with the data previously stored in database.
    """
    SAPSuccessFactorsEnterpriseCustomerConfiguration = apps.get_model(
        'sap_success_factors', 'SAPSuccessFactorsEnterpriseCustomerConfiguration'
    )

    for sap_success_factors_enterprise_configuration in SAPSuccessFactorsEnterpriseCustomerConfiguration.objects.all():
        sap_success_factors_enterprise_configuration.decrypted_key = getattr(
            sap_success_factors_enterprise_configuration, 'key', '')
        sap_success_factors_enterprise_configuration.decrypted_secret = getattr(
            sap_success_factors_enterprise_configuration, 'secret', '')
        sap_success_factors_enterprise_configuration.save()
