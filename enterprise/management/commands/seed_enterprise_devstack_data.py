"""
Management command for assigning enterprise roles to existing enterprise users.
"""

import json
import logging
import textwrap

from django.contrib.auth.models import Group, User
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from django.utils.text import slugify

from enterprise.constants import (
    ENTERPRISE_ADMIN_ROLE,
    ENTERPRISE_CATALOG_ADMIN_ROLE,
    ENTERPRISE_DASHBOARD_ADMIN_ROLE,
    ENTERPRISE_DATA_API_ACCESS_GROUP,
    ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP,
    ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
    ENTERPRISE_LEARNER_ROLE,
    ENTERPRISE_OPERATOR_ROLE,
    ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
)
from enterprise.models import (
    EnterpriseCustomer,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerUser,
    EnterpriseFeatureRole,
    EnterpriseFeatureUserRoleAssignment,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
)

try:
    from student.models import UserProfile
except ImportError:
    UserProfile = None

LOGGER = logging.getLogger(__name__)

CATALOG_CONTENT_FILTER = {
    'content_type': 'courserun',
}


class Command(BaseCommand):
    """
    Management command for populating Devstack with initial data for enterprise.

    Example usage:
        $ ./manage.py lms seed_enterprise_devstack_data
    """
    help = '''
    Seeds an enterprise customer, users of various roles and permissions initial
    data in devstack for related Enterprise models.
    '''

    def _get_default_site(self):
        """ Gets or creates the default devstack site example.com """
        site = Site.objects.get_or_create(name='example.com')
        return site

    def _create_enterprise_customer(self, site):
        """ Gets or creates an EnterpriseCustomer """
        customer_name = 'Test Enterprise'
        enterprise_customer, __ = EnterpriseCustomer.objects.get_or_create(  # pylint: disable=no-member
            name=customer_name,
            site_id=site.id,
            country='US',
            slug=slugify(customer_name),
            enable_data_sharing_consent=True,
            enable_portal_code_management_screen=True,
            enable_portal_reporting_config_screen=True,
            enable_portal_saml_configuration_screen=True,
        )
        return enterprise_customer

    def _create_catalog_for_enterprise(self, enterprise_customer):
        """ Gets or creates a catalog for an EnterpriseCustomer """
        catalog, __ = EnterpriseCustomerCatalog.objects.get_or_create(
            title='All Course Runs',
            enterprise_customer=enterprise_customer,
            content_filter=CATALOG_CONTENT_FILTER,
        )
        return catalog

    def _create_enterprise_data_api_group(self):
        """ Ensures the `ENTERPRISE_DATA_API_ACCESS_GROUP` is created """
        Group.objects.get_or_create(name=ENTERPRISE_DATA_API_ACCESS_GROUP)

    def _create_enterprise_enrollment_api_group(self):
        """ Ensures the `ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP` is created """
        Group.objects.get_or_create(name=ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP)

    def _create_enterprise_user(self, username, role):
        """
        Creates a new user with the specified `username` and `role` (e.g.,
        'enterprise_learner'). The newly created user is added to the
        appropriate Django groups (e.g., data api access) and creates
        system-wide and feature role assignments.
        """
        valid_roles = [
            ENTERPRISE_LEARNER_ROLE,
            ENTERPRISE_ADMIN_ROLE,
            ENTERPRISE_OPERATOR_ROLE,
        ]
        if role in valid_roles:
            is_staff = role == ENTERPRISE_OPERATOR_ROLE
            try:
                user = User.objects.create_user(
                    email='{username}@example.com'.format(username=username),
                    username=username,
                    password='edx',
                    is_staff=is_staff,
                )
            except IntegrityError:
                # If a user we attempt to create in this method already exists but with
                # slightly different parameters, we will attempt to use the existing user.
                user = User.objects.get(username=username)
            if user:
                self._add_name_to_user_profile(user)
                self._add_user_to_groups(user=user, role=role)
                self._create_system_wide_role_assignment(user=user, role=role)
                self._create_feature_role_assignments(user=user, role=role)
                return {
                    "user": user,
                    "role": role,
                }
        else:
            LOGGER.warning('\nUser not created. Role %s not recognized.', role)
        return None

    def _add_name_to_user_profile(self, user):
        """ Adds a name to a user's profile. """
        if not UserProfile:
            LOGGER.error('UserProfile module does not exist.')
            return
        UserProfile.objects.update_or_create(
            user=user,
            defaults={'name': 'Test Enterprise User'},
        )

    def _add_user_to_groups(self, user, role):
        """ Adds a user with a given role to the appropriate groups """
        if role == ENTERPRISE_LEARNER_ROLE:
            return
        data_api_group = Group.objects.get(name=ENTERPRISE_DATA_API_ACCESS_GROUP)
        data_api_group.user_set.add(user)
        enrollment_api_group = Group.objects.get(name=ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP)
        enrollment_api_group.user_set.add(user)

    def _create_system_wide_role_assignment(self, user, role):
        """
        Gets or creates a system-wide role assignment for the specified user and role
        """
        system_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=role)
        SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
            user=user,
            role=system_role,
        )

    def _create_feature_role_assignments(self, user, role):
        """
        Gets or creates a feature role assignment for the specified user and role
        """
        if role == ENTERPRISE_LEARNER_ROLE:
            return
        feature_roles = [
            ENTERPRISE_CATALOG_ADMIN_ROLE,
            ENTERPRISE_DASHBOARD_ADMIN_ROLE,
            ENTERPRISE_ENROLLMENT_API_ADMIN_ROLE,
            ENTERPRISE_REPORTING_CONFIG_ADMIN_ROLE,
        ]
        for feature_role in feature_roles:
            feature_role_obj, __ = EnterpriseFeatureRole.objects.get_or_create(name=feature_role)
            EnterpriseFeatureUserRoleAssignment.objects.get_or_create(
                user=user,
                role=feature_role_obj,
            )

    def _create_enterprise_customer_user(self, username, enterprise_customer):
        """
        Gets or creates an EnterpriseCustomerUser associated with an EnterpriseCustomer
        """
        user, __ = User.objects.get_or_create(username=username)
        enterprise_customer_user, __ = EnterpriseCustomerUser.objects.get_or_create(
            user_id=user.pk,
            enterprise_customer=enterprise_customer,
        )
        return enterprise_customer_user

    def _create_enterprise(self, enterprise_users):
        """
        Creates an enterprise and its associated data, including the
        EnterpriseCustomer, an enterprise catalog, and initial users of
        varying roles.
        """
        site, __ = self._get_default_site()
        enterprise_customer = self._create_enterprise_customer(site=site)
        enterprise_catalog = self._create_catalog_for_enterprise(
            enterprise_customer=enterprise_customer
        )
        enterprise_linked_users = []
        for enterprise_user in enterprise_users:
            enterprise_user_obj = self._create_enterprise_customer_user(
                username=enterprise_user['user'].username,
                enterprise_customer=enterprise_customer,
            )
            enterprise_linked_users.append({
                "enterprise_customer_user": enterprise_user_obj,
                "enterprise_role": enterprise_user['role'],
            })

        return {
            "enterprise_customer": enterprise_customer,
            "enterprise_catalog": enterprise_catalog,
            "enterprise_linked_users": enterprise_linked_users,
        }

    def handle(self, *args, **options):
        """
        Entry point for managment command execution.
        """
        LOGGER.info(
            '\nEnsuring enterprise-related Django groups (%s, %s) exist...',
            ENTERPRISE_DATA_API_ACCESS_GROUP,
            ENTERPRISE_ENROLLMENT_API_ACCESS_GROUP,
        )
        self._create_enterprise_data_api_group()
        self._create_enterprise_enrollment_api_group()

        LOGGER.info('\nCreating enterprise users and assigning roles...')
        # Create one of each enterprise user type (i.e., learner, admin, operator)
        enterprise_users = [
            self._create_enterprise_user(
                username=ENTERPRISE_LEARNER_ROLE,
                role=ENTERPRISE_LEARNER_ROLE,
            ),
            self._create_enterprise_user(
                username=ENTERPRISE_ADMIN_ROLE,
                role=ENTERPRISE_ADMIN_ROLE,
            ),
            self._create_enterprise_user(
                username=ENTERPRISE_OPERATOR_ROLE,
                role=ENTERPRISE_OPERATOR_ROLE
            ),
        ]
        # Add a couple more learners!
        for i in range(2):
            enterprise_users.append(self._create_enterprise_user(
                username='{role}_{index}'.format(
                    role=ENTERPRISE_LEARNER_ROLE,
                    index=i + 1,
                ),
                role=ENTERPRISE_LEARNER_ROLE
            ))

        LOGGER.info('\nCreating a new enterprise...')
        enterprise = self._create_enterprise(enterprise_users=enterprise_users)

        # generate a json serializable list of linked enterprise users
        enterprise_linked_users = []
        for item in enterprise['enterprise_linked_users']:
            ecu = item['enterprise_customer_user']
            enterprise_linked_users.append({
                'user_id': ecu.user_id,
                'enterprise_customer_user_id': ecu.id,
            })

        LOGGER.info(
            textwrap.dedent(
                '''\nSuccessfully created a new enterprise with the following data:
                \n| Enterprise Customer: %s (%s)
                \n| Enterprise Catalog: %s (%s)
                \n| Enterprise Users (%i): %s
                '''
            ),
            enterprise['enterprise_customer'].name,
            enterprise['enterprise_customer'].uuid,
            enterprise['enterprise_catalog'].title,
            enterprise['enterprise_catalog'].uuid,
            len(enterprise_linked_users),
            json.dumps(enterprise_linked_users, sort_keys=True, indent=2),
        )
