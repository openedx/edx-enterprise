"""
Module for defining models needed for configuration of internal
concerns like management command options and parameters.
"""
from config_models.models import ConfigurationModel

from django.db import models
from django.utils.translation import ugettext_lazy as _

from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE,
)


# pylint: disable=feature-toggle-needs-doc
# This is not a feature toggle.
class UpdateRoleAssignmentsWithCustomersConfig(ConfigurationModel):
    """
    Model that specifies parameters for the
    ``update_role_assignments_with_customers`` management command.

    .. no_pii:
    """
    class Meta:
        app_label = 'enterprise'

    ROLE_CHOICES = [
        (ENTERPRISE_ADMIN_ROLE, ENTERPRISE_ADMIN_ROLE),
        (ENTERPRISE_LEARNER_ROLE, ENTERPRISE_LEARNER_ROLE),
        (SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE, SYSTEM_ENTERPRISE_CATALOG_ADMIN_ROLE),
        (ENTERPRISE_OPERATOR_ROLE, ENTERPRISE_OPERATOR_ROLE),
    ]
    role = models.CharField(
        blank=True,
        choices=ROLE_CHOICES,
        max_length=100,
        help_text=_('Specifies which user role assignments to update.  If unspecified, will update for all roles.'),
    )
    batch_size = models.IntegerField(
        default=500,
        help_text=_('Number of user role asssignments to update in each batch of updates.'),
    )
    enterprise_customer_uuid = models.CharField(
        blank=True,
        max_length=36,
        help_text=_('The enterprise customer to limit role assignments to.'),
    )
    dry_run = models.BooleanField(
        default=True,
        help_text=_(
            'If set, no updates or creates will occur; will instead iterate over '
            'the assignments that would be modified or created'
        ),
    )
