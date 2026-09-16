"""
Management command for ensuring any pending group membership, ie memberships associated with a pending enterprise user,
are removed after 90 days.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand

from enterprise.models import EnterpriseCustomer, EnterpriseGroupMembership
from enterprise.utils import localized_utcnow

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command for ensuring any pending group membership, ie memberships associated with a pending enterprise
    user, are removed after 90 days. Optionally supply a ``--enterprise_customer`` arg to only run this command on
    a singular customer.

    Example usage:
        $ ./manage.py remove_expired_pending_group_memberships
    """
    help = 'Removes pending group memberships if they are older than 90 days.'

    def add_arguments(self, parser):
        parser.add_argument("-e", "--enterprise_customer")

    def handle(self, *args, **options):
        queryset = EnterpriseGroupMembership.all_objects.all()
        if enterprise_arg := options.get("enterprise_customer"):
            try:
                enterprise_customer = EnterpriseCustomer.objects.get(uuid=enterprise_arg)
                queryset = queryset.filter(group__enterprise_customer=enterprise_customer)
            except EnterpriseCustomer.DoesNotExist as exc:
                log.exception(f'Enterprise Customer: {enterprise_arg} not found')
                raise exc
        expired_memberships = queryset.filter(
            enterprise_customer_user=None,
            pending_enterprise_customer_user__isnull=False,
            created__lte=localized_utcnow() - timedelta(days=90)
        )
        for membership in expired_memberships:
            pecu_to_delete = membership.pending_enterprise_customer_user
            pecu_to_delete.delete()
            membership.refresh_from_db()
            # https://github.com/jazzband/django-model-utils/blob/master/model_utils/models.py#L133-L158
            membership.delete(soft=False)
