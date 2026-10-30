"""
Utilities for Blackboard integrated channels.
"""


def populate_decrypted_fields_blackboard(apps, schema_editor=None):  # pylint: disable=unused-argument
    """
    Populates the encryption fields in Blackboard config with the data previously stored in database.
    """
    BlackboardEnterpriseCustomerConfiguration = apps.get_model(
        'blackboard', 'BlackboardEnterpriseCustomerConfiguration'
    )

    for blackboard_enterprise_configuration in BlackboardEnterpriseCustomerConfiguration.objects.all():
        blackboard_enterprise_configuration.decrypted_client_id = getattr(
            blackboard_enterprise_configuration, 'client_id', '')
        blackboard_enterprise_configuration.decrypted_client_secret = getattr(
            blackboard_enterprise_configuration, 'client_secret', '')
        blackboard_enterprise_configuration.save()
