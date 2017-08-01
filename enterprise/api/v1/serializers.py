"""
Serializers for enterprise api version 1.
"""

from __future__ import absolute_import, unicode_literals

from rest_framework import serializers

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _

from enterprise import models, utils


class ImmutableStateSerializer(serializers.Serializer):
    """
    Base serializer for any serializer that inhibits state changing requests.
    """

    def create(self, validated_data):
        """
        Do not perform any operations for state changing requests.
        """
        pass

    def update(self, instance, validated_data):
        """
        Do not perform any operations for state changing requests.
        """
        pass


class ResponsePaginationSerializer(ImmutableStateSerializer):
    """
    Serializer for responses that require pagination.
    """

    count = serializers.IntegerField(read_only=True, help_text=_('Total count of items.'))
    next = serializers.CharField(read_only=True, help_text=_('URL to fetch next page of items.'))
    previous = serializers.CharField(read_only=True, help_text=_('URL to fetch previous page of items.'))
    results = serializers.ListField(read_only=True, help_text=_('List of items.'))


class SiteSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``Site`` model.
    """

    class Meta:
        model = Site
        fields = (
            'domain', 'name',
        )


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``User`` model.
    """

    class Meta:
        model = User
        fields = (
            'id', 'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'date_joined'
        )


class EnterpriseCustomerBrandingConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``EnterpriseCustomerBrandingConfiguration`` model.
    """

    class Meta:
        model = models.EnterpriseCustomerBrandingConfiguration
        fields = (
            'enterprise_customer', 'logo'
        )


class EnterpriseCustomerEntitlementSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``EnterpriseCustomerEntitlement`` model.
    """

    class Meta:
        model = models.EnterpriseCustomerEntitlement
        fields = (
            'enterprise_customer', 'entitlement_id'
        )


class EnterpriseCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``EnterpriseCustomer`` model.
    """

    site = SiteSerializer()
    branding_configuration = EnterpriseCustomerBrandingConfigurationSerializer()
    enterprise_customer_entitlements = EnterpriseCustomerEntitlementSerializer(  # pylint: disable=invalid-name
        many=True,
    )

    class Meta:
        model = models.EnterpriseCustomer
        fields = (
            'uuid', 'name', 'catalog', 'active', 'site', 'enable_data_sharing_consent', 'enforce_data_sharing_consent',
            'enterprise_customer_users', 'branding_configuration', 'enterprise_customer_entitlements',
            'enable_audit_enrollment'
        )


class EnterpriseCourseEnrollmentReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for the ``EnterpriseCourseEnrollment`` model.
    """

    class Meta:
        model = models.EnterpriseCourseEnrollment
        fields = (
            'enterprise_customer_user', 'consent_granted', 'course_id'
        )


class EnterpriseCourseEnrollmentWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for writing to the ``EnterpriseCourseEnrollment`` model.
    """

    username = serializers.CharField(max_length=30)
    enterprise_customer_user = None

    class Meta:
        model = models.EnterpriseCourseEnrollment
        fields = (
            'username', 'course_id', 'consent_granted'
        )

    def validate_username(self, value):
        """
        Verify that the username has a matching user, and that the user has an associated EnterpriseCustomerUser.
        """
        try:
            user = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")

        try:
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.get(user_id=user.pk)
        except models.EnterpriseCustomerUser.DoesNotExist:
            raise serializers.ValidationError("User has no EnterpriseCustomerUser")

        self.enterprise_customer_user = enterprise_customer_user
        return value

    def save(self):  # pylint: disable=arguments-differ
        """
        Save the model with the found EnterpriseCustomerUser.
        """
        course_id = self.validated_data['course_id']
        consent_granted = self.validated_data['consent_granted']

        models.EnterpriseCourseEnrollment.objects.get_or_create(
            enterprise_customer_user=self.enterprise_customer_user,
            course_id=course_id,
            consent_granted=consent_granted,
        )


class UserDataSharingConsentAuditSerializer(serializers.ModelSerializer):
    """
    Serializer for the ``UserDataSharingConsentAudit`` model.
    """

    class Meta:
        model = models.UserDataSharingConsentAudit
        fields = (
            'user', 'state', 'enabled'
        )


class EnterpriseCustomerUserReadOnlySerializer(serializers.ModelSerializer):
    """
    Serializer for the ``EnterpriseCustomerUser`` model.
    """

    user = UserSerializer()
    enterprise_customer = EnterpriseCustomerSerializer()
    data_sharing_consent = UserDataSharingConsentAuditSerializer(many=True)

    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'id', 'enterprise_customer', 'user_id', 'user', 'data_sharing_consent'
        )


class EnterpriseCustomerUserWriteSerializer(serializers.ModelSerializer):
    """
    Serializer for writing to the ``EnterpriseCustomerUser`` model.
    """

    username = serializers.CharField(max_length=30)
    user = None

    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'enterprise_customer', 'username'
        )

    def validate_username(self, value):
        """
        Verify that the username has a matching user.
        """
        try:
            self.user = User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")

        return value

    def save(self):  # pylint: disable=arguments-differ
        """
        Save the EnterpriseCustomerUser.
        """
        enterprise_customer = self.validated_data['enterprise_customer']

        ecu = models.EnterpriseCustomerUser(
            user_id=self.user.pk,
            enterprise_customer=enterprise_customer,
        )
        ecu.save()


class EnterpriseCustomerUserEntitlementSerializer(ImmutableStateSerializer):
    """
    Serializer for the entitlements of ``EnterpriseCustomerUser``.

    This Serializer is for read only endpoint of enterprise learner's entitlements
    It will ignore any state changing requests like POST, PUT and PATCH.
    """

    entitlements = serializers.ListField(child=serializers.DictField())
    user = UserSerializer(read_only=True)
    enterprise_customer = EnterpriseCustomerSerializer(read_only=True)
    data_sharing_consent = UserDataSharingConsentAuditSerializer(many=True, read_only=True)


class EnterpriseCourseCatalogReadOnlySerializer(ImmutableStateSerializer):
    """
    Serializer for ``enterprise.api.v1.views.EnterpriseCatalogViewSet``.
    """

    # pylint: disable=invalid-name
    id = serializers.IntegerField(read_only=True, help_text=_('Enterprise course catalog primary key.'))
    name = serializers.CharField(help_text=_('Catalog name'))
    query = serializers.CharField(help_text=_('Query to retrieve catalog contents'))
    courses_count = serializers.IntegerField(read_only=True, help_text=_('Number of courses contained in this catalog'))
    viewers = serializers.ListField(
        allow_null=True, allow_empty=True, required=False,
        help_text=_('Usernames of users with explicit access to view this catalog'),
        style={'base_template': 'input.html'},
        child=serializers.CharField(),
    )


class EnterpriseCoursesReadOnlySerializer(ResponsePaginationSerializer):
    """
    Serializer for courses embodied by various endpoint's responses.
    """

    def update_enterprise_courses(self, enterprise_customer, **kwargs):
        """
        This method adds enterprise specific metadata for each course.

        Arguments:
            enterprise_customer (EnterpriseCustomer): ``EnterpriseCustomer`` instance.
            kwargs: Anything extra to update the enterprise context with.

        We are adding following field in all the courses.
            tpa_hint: a string for identifying Identity Provider.
        """
        courses = []

        global_context = {
            'tpa_hint': enterprise_customer and enterprise_customer.identity_provider,
            'enterprise_id': enterprise_customer and enterprise_customer.uuid,
        }
        global_context.update(**kwargs)

        for course in self.data['results']:
            courses.append(
                self.update_course(course, enterprise_customer, global_context)
            )
        self.data['results'] = courses

    def update_course(self, course, enterprise_customer, global_context, **kwargs):
        """
        Update course metadata of the given course and return updated course.

        Arguments:
            course (dict): Course Metadata returned by course catalog API
            enterprise_customer (EnterpriseCustomer): ``EnterpriseCustomer`` instance.
            global_context (dict): Global attributes that should be added to all the courses.
            kwargs: Anything extra to update the enterprise context with.

        Returns:
            (dict): Updated course metadata
        """
        # extract course runs from course metadata and
        # Replace course's course runs with the updated course runs
        course['course_runs'] = self.update_course_runs(
            course_runs=course.get('course_runs') or [],
            enterprise_customer=enterprise_customer,
            **kwargs
        )

        enterprise_context = {
            'tpa_hint': enterprise_customer and enterprise_customer.identity_provider,
            'enterprise_id': enterprise_customer and enterprise_customer.uuid,
        }
        enterprise_context.update(**kwargs)

        # Update marketing urls in course metadata to include enterprise related info.
        if course.get('marketing_url'):
            course.update({
                "marketing_url": utils.update_query_parameters(course.get('marketing_url'), enterprise_context),
            })

        # now add global context to the course.
        course.update(global_context)
        return course

    def update_course_runs(self, course_runs, enterprise_customer, **kwargs):
        """
        Update Marketing urls in course metadata adn return updated course.

        Arguments:
            course_runs (list): List of course runs.
            enterprise_customer (EnterpriseCustomer): ``EnterpriseCustomer`` instance.
            kwargs: Anything extra to update the enterprise context with.

        Returns:
            (dict): Dictionary containing updated course metadata.
        """
        updated_course_runs = []

        enterprise_context = {
            'tpa_hint': enterprise_customer and enterprise_customer.identity_provider,
            'enterprise_id': enterprise_customer and enterprise_customer.uuid,
        }
        enterprise_context.update(**kwargs)

        for course_run in course_runs:
            track_selection_url = utils.get_course_track_selection_url(
                course_run=course_run,
                query_parameters=enterprise_context,
            )

            enrollment_url = enterprise_customer.get_course_enrollment_url(course_run.get('key'))

            # Add/update track selection url in course run metadata.
            course_run.update({
                'track_selection_url': track_selection_url,
                'enrollment_url': enrollment_url
            })

            # Update marketing urls in course metadata to include enterprise related info.
            if course_run.get('marketing_url'):
                course_run.update({
                    "marketing_url": utils.update_query_parameters(
                        course_run.get('marketing_url'), enterprise_context
                    ),
                })

            # Add updated course run to the list.
            updated_course_runs.append(course_run)

        return updated_course_runs


class EnterpriseProgramsReadOnlySerializer(ImmutableStateSerializer):
    """
    Serializer for ``enterprise.api.v1.views.EnterpriseProgramsViewSet``.
    """

    def update_program_results(self):
        """
        Update the serializer's Program data results to have proper Enterprise context.
        """
        program = self.data.get('results', [{}])[0]
        self.data['results'] = self.update_program(program)

    def update_program_list_results(self):
        """
        Update the serializer's list of Program data results to have proper Enterprise context.
        """
        program_list = self.data.get('results', [])
        self.data['results'] = self.update_program_list(program_list)

    def update_program(self, program):
        """
        Update a Program to add and remove related and unrelated Enterprise context, respectively.

        :param program: The Program to update.
        :return: A Program updated with the appropriate Enterprise context, or whatever data the serializer initialized.
        """
        if not program['is_program_eligible_for_one_click_purchase']:
            return {}
        # TODO: Add/remove enterprise-related context for the program dict.

    def update_program_list(self, programs):
        """
        Update a set of Programs to add and remove related and unrelated Enterprise context in each, respectively.

        :param programs: The list of Programs to update.
        :return: A list of Programs updated with the appropriate Enterprise context, or whatever data the serializer
                 initialized.
        """
        updated_programs = []
        for program in programs:
            program = self.update_program(program)
            updated_programs.append(program)
        return updated_programs


class EnterprisePaginatedProgramsReadOnlySerializer(EnterpriseProgramsReadOnlySerializer, ResponsePaginationSerializer):
    """
    Serializer for paginating Program results.
    """
    pass
