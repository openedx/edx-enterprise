"""
Django management command to validate that DefaultEnterpriseEnrollmentIntention
objects have enrollable content.
"""
import logging
from datetime import timedelta

from django.core.management import BaseCommand, CommandError
from django.db.models import DateTimeField, Max
from django.db.models.functions import Cast, Coalesce, Greatest
from django.utils import timezone

from enterprise.content_metadata.api import get_and_cache_customer_content_metadata
from enterprise.models import DefaultEnterpriseEnrollmentIntention

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Enumerate the catalog filters and log information about how we might migrate them.
    """

    def __init__(self, *args, **kwargs):
        self.delay_minutes = None
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            '--delay-minutes',
            dest='delay_minutes',
            required=False,
            type=int,
            default=30,
            help="How long after a customer's catalog has been updated are we allowed to evaluate the customer."
        )

    @property
    def latest_change_allowed(self):
        return timezone.now() - timedelta(minutes=self.delay_minutes)

    def handle_intention(self, intention):
        """
        Check that the default enrollment intention's content_key is contained in any of the customer's catalogs.

        Returns:
            dict: Results dict that indicates whether evaluation was skipped, and whether the intention was valid.
        """
        customer = intention.enterprise_customer
        result = {
            'skipped': None,
            'invalid': None,
        }

        if not intention.catalogs_modified_latest:
            result['skipped'] = True
            logger.info(
                f"handle_intention(): SKIPPING Evaluating enrollment intention {intention} "
                "for not having any related catalogs."
            )
            return result
        if intention.catalogs_modified_latest > self.latest_change_allowed:
            result['skipped'] = True
            logger.info(
                f"handle_intention(): SKIPPING Evaluating enrollment intention {intention} "
                "for having catalogs which have been too recently updated."
            )
            return result
        result['skipped'] = False
        logger.info(f"handle_intention(): Evaluating enrollment intention {intention}.")

        content_metadata = get_and_cache_customer_content_metadata(
            customer.uuid,
            intention.content_key,
        )
        contained_in_customer_catalogs = bool(content_metadata)
        if contained_in_customer_catalogs:
            logger.info(
                f"handle_default_enrollment_intention(): Default enrollment intention {intention} "
                "is compatible with the customer's catalogs."
            )
            result["invalid"] = False
        else:
            logger.error(
                f"handle_default_enrollment_intention(): Default enrollment intention {intention} "
                "is NOT compatible with the customer's catalogs."
            )
            result["invalid"] = True
        return result

    def handle(self, *args, **options):
        self.delay_minutes = options.get("delay_minutes")

        intentions = DefaultEnterpriseEnrollmentIntention.objects.select_related(
            'enterprise_customer'
        ).prefetch_related(
            'enterprise_customer__enterprise_customer_catalogs'
        ).annotate(
            catalogs_modified_latest=Greatest(
                Max("enterprise_customer__enterprise_customer_catalogs__modified"),
                Coalesce(
                    Max("enterprise_customer__enterprise_customer_catalogs__enterprise_catalog_query__modified"),
                    # Note 1: Arbitrarily fallback to 1 year ago because Greatest() in MySQL relies on non-null inputs.
                    # Note 2: Cast python datetime to django field type, or else experience weird errors in prod.
                    Cast(timezone.now() - timedelta(days=360), DateTimeField())
                )
            )
        )

        results = {intention: self.handle_intention(intention) for intention in intentions}
        results_evaluated = {intention: result for intention, result in results.items() if not result['skipped']}
        results_invalid = {intention: result for intention, result in results_evaluated.items() if result['invalid']}

        count_total = len(results)
        count_evaluated = len(results_evaluated)
        count_skipped = count_total - count_evaluated
        count_invalid = len(results_invalid)
        count_passed = count_evaluated - count_invalid

        invalid_intentions = results_invalid.keys()

        logger.info(
            f"{count_total} total enrollment intentions found, "
            f"and {count_evaluated}/{count_total} were evaluated "
            f"({count_skipped}/{count_total} skipped)."
        )
        logger.info(
            f"Out of {count_evaluated} total evaluated enrollment intentions, "
            f"{count_passed}/{count_evaluated} passed validation "
            f"({count_invalid}/{count_evaluated} invalid)."
        )
        if count_invalid > 0:
            logger.error(f"Summary of all {count_invalid} invalid intentions: {invalid_intentions}")
            logger.error("FAILURE: Some default enrollment intentions were invalid.")
            raise CommandError(f"{count_invalid} invalid default enrollment intentions found.")
        logger.info("SUCCESS: All default enrollment intentions are valid!")
