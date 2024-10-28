"""
Views for default enterprise enrollments.
"""

from uuid import UUID

from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import status, viewsets
from edx_rbac.mixins import PermissionRequiredForListingMixin

from django.contrib.auth import get_user_model

from enterprise import models
from enterprise.api.v1 import serializers
from enterprise.api.v1.views.base_views import EnterpriseViewSet
from enterprise.constants import (
    DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_PERMISSION,
    DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_ROLE,
)


class DefaultEnterpriseEnrollmentIntentionViewSet(
    PermissionRequiredForListingMixin,
    EnterpriseViewSet,
    viewsets.ModelViewSet,
):
    """
    API views for default enterprise enrollment intentions
    """

    permission_required = DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_PERMISSION
    list_lookup_field = 'enterprise_customer__uuid'
    allowed_roles = [DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_ROLE]
    serializer_class = serializers.DefaultEnterpriseEnrollmentIntentionSerializer
    http_method_names = ['get', 'post', 'delete']

    @property
    def requested_enterprise_customer_uuid(self):
        """
        Get and validate the enterprise customer UUID from the query parameters.
        """
        if not (enterprise_customer_uuid := self.request.query_params.get('enterprise_customer_uuid')):
            raise ValidationError({"detail": "enterprise_customer_uuid is a required query parameter."})

        try:
            return UUID(enterprise_customer_uuid)
        except ValueError as exc:
            raise ValidationError({
                "detail": "enterprise_customer_uuid query parameter is not a valid UUID."
            }) from exc

    @property
    def requested_lms_user_id(self):
        """
        Get the (optional) LMS user ID from the request.
        """
        return self.request.query_params.get('lms_user_id')

    @property
    def base_queryset(self):
        """
        Required by the `PermissionRequiredForListingMixin`.
        For non-list actions, this is what's returned by `get_queryset()`.
        For list actions, some non-strict subset of this is what's returned by `get_queryset()`.
        """
        kwargs = {}
        if self.requested_enterprise_customer_uuid:
            kwargs['enterprise_customer'] = self.requested_enterprise_customer_uuid
        return models.DefaultEnterpriseEnrollmentIntention.objects.filter(**kwargs)

    @property
    def user_for_learner_status(self):
        """
        Get the user for learner status based on the request.
        """
        if self.request.user.is_staff and self.requested_lms_user_id is not None:
            # If the user is staff and a lms_user_id is provided, return the specified user.
            User = get_user_model()
            try:
                return User.objects.get(id=self.requested_lms_user_id)
            except User.DoesNotExist:
                return None

        # Otherwise, return the request user.
        return self.request.user

    def get_permission_object(self):
        """
        Used for "retrieve" actions. Determines the context (enterprise UUID) to check
        against for role-based permissions.
        """
        return str(self.requested_enterprise_customer_uuid)

    @action(detail=False, methods=['get'], url_path='learner-status')
    def learner_status(self, request):  # pylint: disable=unused-argument
        """
        Get the status of the learner's enrollment in the default enterprise course.
        """
        # Validate the enterprise customer uuid.
        try:
            enterprise_customer_uuid = self.requested_enterprise_customer_uuid
        except ValidationError as exc:
            return Response(exc, status=status.HTTP_400_BAD_REQUEST)

        # Validate the user for learner status exists and is associated
        # with the enterprise customer.
        if not (user_for_learner_status := self.user_for_learner_status):
            return Response(
                {'detail': f'User with lms_user_id {self.requested_lms_user_id} not found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.get(
                user_id=user_for_learner_status.id,
                enterprise_customer=enterprise_customer_uuid,
            )
        except models.EnterpriseCustomerUser.DoesNotExist:
            return Response(
                {
                    'detail': (
                        f'User with lms_user_id {user_for_learner_status.id} is not associated with '
                        f'the enterprise customer {enterprise_customer_uuid}.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve configured default enrollment intentions for the enterprise customer
        default_enrollment_intentions_for_customer = models.DefaultEnterpriseEnrollmentIntention.objects.filter(
            enterprise_customer=enterprise_customer_uuid,
        )

        # Retrieve the course enrollments for the learner
        enterprise_course_enrollments_for_learner = models.EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=enterprise_customer_user,
        )

        serializer_data = {
            'lms_user_id': user_for_learner_status.id,
            'user_email': user_for_learner_status.email,
            'enterprise_customer_uuid': enterprise_customer_uuid,
        }
        serializer = serializers.DefaultEnterpriseEnrollmentIntentionLearnerStatusSerializer(
            data=serializer_data,
            context=self._get_serializer_context_for_learner_status(
                default_enrollment_intentions_for_customer,
                enterprise_course_enrollments_for_learner,
            ),
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _course_ids_for_active_enterprise_course_enrollments(self, enterprise_course_enrollments):
        """
        Get active enterprise course enrollments (i.e., actively enrolled, not audit).
        """
        return [
            enrollment.course_id
            for enrollment in enterprise_course_enrollments
            if enrollment.is_active and not enrollment.is_audit_enrollment
        ]

    def _get_serializer_context_for_learner_status(
            self,
            default_enrollment_intentions_for_customer,
            enterprise_course_enrollments_for_learner,
        ):
        """
        Get the serializer context for learner status, grouping the  default enrollment intentions
        based on the learner's enrollment status and whether the course run is currently enrollable.
        """
        already_enrolled = []
        needs_enrollment_enrollable = []
        needs_enrollment_not_enrollable = []

        enrolled_course_ids_for_learner = self._course_ids_for_active_enterprise_course_enrollments(
            enterprise_course_enrollments_for_learner
        )

        # Iterate through the default enrollment intentions and categorize them based
        # on the learner's enrollment status (already enrolled, needs enrollment, etc.)
        # and whether the course run is enrollable.
        for default_enrollment_intention in default_enrollment_intentions_for_customer:
            course_run_key = default_enrollment_intention.course_run_key
            is_course_run_enrollable = default_enrollment_intention.is_course_run_enrollable
            applicable_enterprise_catalog_uuids = default_enrollment_intention.applicable_enterprise_catalog_uuids

            if course_run_key in enrolled_course_ids_for_learner:
                # Learner is already enrolled in this course run
                already_enrolled.append(default_enrollment_intention)
            elif is_course_run_enrollable and applicable_enterprise_catalog_uuids:
                # Learner needs enrollment, the course run is enrollable, and there are applicable catalogs
                needs_enrollment_enrollable.append(default_enrollment_intention)
            else:
                # Learner needs enrollment, but the course run is not enrollable and/or there are no applicable catalogs
                needs_enrollment_not_enrollable.append(default_enrollment_intention)

        return {
            'needs_enrollment': {
                'enrollable': needs_enrollment_enrollable,
                'not_enrollable': needs_enrollment_not_enrollable,
            },
            'already_enrolled': already_enrolled,
        }
