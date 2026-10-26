"""
Management command for enrolling a learner in a course under a specific enterprise customer.
"""

import logging

from django.contrib import auth
from django.core.management.base import BaseCommand, CommandError

from enterprise.devstack_api import enroll_learner_in_course
from enterprise.models import EnterpriseCustomer, EnterpriseCustomerUser

LOGGER = logging.getLogger(__name__)
User = auth.get_user_model()


class Command(BaseCommand):
    """
    Management command for enrolling a learner in a course under a specific enterprise customer.

    Creates a platform CourseEnrollment, an EnterpriseCourseEnrollment, and a
    DataSharingConsent record. The DSC record is ungranted by default; pass
    --grant-dsc to mark it as granted.

    Requires the learner to already be linked to the enterprise (via
    EnterpriseCustomerUser). Run create_enterprise_linked_learner first if needed.

    Example usage:
        $ ./manage.py lms enroll_enterprise_learner \
              --username my_learner \
              --course-id course-v1:edX+DemoX+Demo_Course \
              --enterprise-name "Test Enterprise"

        $ ./manage.py lms enroll_enterprise_learner \
              --username my_learner \
              --course-id course-v1:edX+DemoX+Demo_Course \
              --enterprise-name "Other Enterprise" \
              --grant-dsc
    """

    help = 'Enroll a learner in a course under a specific enterprise customer.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            required=True,
            help='Username of the learner to enroll.',
        )
        parser.add_argument(
            '--course-id',
            required=True,
            dest='course_id',
            help='Course key to enroll the learner in (e.g. course-v1:edX+DemoX+Demo_Course).',
        )
        parser.add_argument(
            '--enterprise-name',
            required=True,
            dest='enterprise_name',
            help='Name of the enterprise customer to link the enrollment to.',
        )
        parser.add_argument(
            '--mode',
            default='audit',
            help='Enrollment mode (default: audit).',
        )
        parser.add_argument(
            '--grant-dsc',
            action='store_true',
            default=False,
            dest='grant_dsc',
            help='Mark the DataSharingConsent record as granted. Default is ungranted.',
        )

    def handle(self, *args, **options):
        username = options['username']
        enterprise_name = options['enterprise_name']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User '{username}' does not exist.") from exc

        try:
            enterprise_customer = EnterpriseCustomer.objects.get(name=enterprise_name)
        except EnterpriseCustomer.DoesNotExist as exc:
            raise CommandError(
                f"EnterpriseCustomer with name '{enterprise_name}' does not exist."
            ) from exc

        try:
            enroll_learner_in_course(
                user=user,
                course_id=options['course_id'],
                enterprise_customer=enterprise_customer,
                mode=options['mode'],
                grant_dsc=options['grant_dsc'],
            )
        except EnterpriseCustomerUser.DoesNotExist as exc:
            raise CommandError(
                f"User '{username}' is not linked to enterprise '{enterprise_name}'. "
                "Run create_enterprise_linked_learner first."
            ) from exc
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        LOGGER.info(
            'Done. Enrolled %s in %s under enterprise "%s" (DSC granted=%s).',
            username, options['course_id'], enterprise_name, options['grant_dsc'],
        )
