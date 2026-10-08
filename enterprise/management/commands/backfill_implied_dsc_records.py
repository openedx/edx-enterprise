"""
Django management command to backfill implied DataSharingConsent records for externally managed customers.
"""
import logging

from edx_django_utils.db import chunked_queryset

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError
from django.db.models import QuerySet

from consent.helpers import get_usernames_with_revoked_data_sharing_consent, grant_implied_data_sharing_consent
from consent.models import DataSharingConsent
from enterprise.models import EnterpriseCourseEnrollment, EnterpriseCustomer

LOGGER = logging.getLogger(__name__)
User = get_user_model()
MESSAGE_FORMAT = 'DSC enterprise: {}, username: {}, course_id: {}'


class Command(BaseCommand):
    """
    Django management command to backfill implied DataSharingConsent records for externally managed customers.

    Customers with externally managed data sharing consent collect consent outside of edX, so their learners
    are never prompted and no consent record is written for their enrollments. Without a consent record these
    enrollments are excluded from learner progress reporting. This command creates a granted consent record for
    every such enrollment that does not have one. Existing consent records, including revoked ones, are left as is,
    so the command is safe to re-run. Learners who revoked consent for any course of the customer are skipped, and so
    are enrollments of unlinked learners, since learner progress reporting excludes them.

    Example usage:
    ./manage.py lms backfill_implied_dsc_records --no-commit
    ./manage.py lms backfill_implied_dsc_records --enterprise-customer-uuid <uuid> --no-commit
    ./manage.py lms backfill_implied_dsc_records --enterprise-customer-uuid <uuid>
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--enterprise-customer-uuid',
            action='store',
            dest='enterprise_customer_uuid',
            default=None,
            help='Only backfill enrollments of this enterprise customer.',
        )
        parser.add_argument(
            '--no-commit',
            action='store_true',
            dest='no_commit',
            default=False,
            help='Dry Run, print log messages without committing anything.',
        )

    def _get_enterprise_customers(self, enterprise_customer_uuid: str | None) -> QuerySet[EnterpriseCustomer]:
        """
        Return the enterprise customers with externally managed data sharing consent to backfill.
        """
        # Keep in sync with `EnterpriseCustomer.implies_data_sharing_consent`.
        enterprise_customers = EnterpriseCustomer.objects.filter(
            enable_data_sharing_consent=True,
            enforce_data_sharing_consent=EnterpriseCustomer.EXTERNALLY_MANAGED,
        )
        if enterprise_customer_uuid:
            enterprise_customers = enterprise_customers.filter(uuid=enterprise_customer_uuid)
            if not enterprise_customers.exists():
                raise CommandError(
                    'Enterprise customer {} does not exist or does not have externally managed '
                    'data sharing consent.'.format(enterprise_customer_uuid)
                )
        return enterprise_customers

    def handle(self, *args, **options):
        should_commit = not options['no_commit']

        LOGGER.info('[Implied DSC Backfill] Process started. Commit: {}'.format(should_commit))

        results = {
            'Created Record Count': 0,
            'Existing Record Count': 0,
            'Skipped No Username Count': 0,
            'Skipped Revoked Consent Count': 0,
        }
        for enterprise_customer in self._get_enterprise_customers(options['enterprise_customer_uuid']):
            customer_created_count = 0
            revoked_usernames = get_usernames_with_revoked_data_sharing_consent(enterprise_customer)
            # The default manager already selects the enterprise customer user and skips unlinked learners.
            enrollments = EnterpriseCourseEnrollment.objects.filter(
                enterprise_customer_user__enterprise_customer=enterprise_customer,
            )
            for chunked_enrollments in chunked_queryset(enrollments):
                chunked_enrollments = list(chunked_enrollments)
                # `EnterpriseCustomerUser.username` queries the user per call, so fetch usernames per chunk instead.
                usernames_by_user_id = dict(User.objects.filter(
                    id__in={enrollment.enterprise_customer_user.user_id for enrollment in chunked_enrollments},
                ).values_list('id', 'username'))
                for enrollment in chunked_enrollments:
                    username = usernames_by_user_id.get(enrollment.enterprise_customer_user.user_id)
                    if not username:
                        results['Skipped No Username Count'] += 1
                        continue
                    if username in revoked_usernames:
                        results['Skipped Revoked Consent Count'] += 1
                        continue

                    if should_commit:
                        created = grant_implied_data_sharing_consent(
                            username=username,
                            course_id=enrollment.course_id,
                            enterprise_customer=enterprise_customer,
                        )
                    else:
                        created = not DataSharingConsent.objects.filter(
                            enterprise_customer=enterprise_customer,
                            username=username,
                            course_id=enrollment.course_id,
                        ).exists()

                    if created:
                        LOGGER.info('[Implied DSC Backfill] {} {}'.format(
                            'Created' if should_commit else 'To be created',
                            MESSAGE_FORMAT.format(enterprise_customer.uuid, username, enrollment.course_id),
                        ))
                        results['Created Record Count'] += 1
                        customer_created_count += 1
                    else:
                        results['Existing Record Count'] += 1

            LOGGER.info('[Implied DSC Backfill] Enterprise customer {}: {} records {}.'.format(
                enterprise_customer.uuid,
                customer_created_count,
                'created' if should_commit else 'to be created',
            ))

        LOGGER.info('[Implied DSC Backfill] Execution completed.\nResults: {}'.format(results))
