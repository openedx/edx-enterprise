"""
Views for default enterprise enrollments.
"""

from uuid import UUID

from edx_rbac.mixins import PermissionRequiredForListingMixin
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.functional import cached_property

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
    viewsets.ReadOnlyModelViewSet,
):
    """
    API views for default enterprise enrollment intentions
    """

    permission_required = DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_PERMISSION
    list_lookup_field = 'enterprise_customer__uuid'
    allowed_roles = [DEFAULT_ENTERPRISE_ENROLLMENT_INTENTIONS_ROLE]
    serializer_class = serializers.DefaultEnterpriseEnrollmentIntentionSerializer

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
        return models.DefaultEnterpriseEnrollmentIntention.available_objects.filter(
            enterprise_customer=self.requested_enterprise_customer_uuid,
        )

    @cached_property
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
    def learner_status(self, request):
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
        if not self.user_for_learner_status:
            return Response(
                {'detail': f'User with lms_user_id {self.requested_lms_user_id} not found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            enterprise_customer_user = models.EnterpriseCustomerUser.objects.get(
                user_id=self.user_for_learner_status.id,
                enterprise_customer=enterprise_customer_uuid,
            )
        except models.EnterpriseCustomerUser.DoesNotExist:
            return Response(
                {
                    'detail': (
                        f'User with lms_user_id {self.user_for_learner_status.id} is not associated with '
                        f'the enterprise customer {enterprise_customer_uuid}.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve configured default enrollment intentions for the enterprise customer
        default_enrollment_intentions_for_customer = (
            models.DefaultEnterpriseEnrollmentIntention.available_objects.filter(
                enterprise_customer=enterprise_customer_uuid,
            )
        )

        # Retrieve the course enrollments for the learner
        enterprise_course_enrollments_for_learner = models.EnterpriseCourseEnrollment.objects.filter(
            enterprise_customer_user=enterprise_customer_user,
        )

        serializer_data = {
            'lms_user_id': self.user_for_learner_status.id,
            'user_email': self.user_for_learner_status.email,
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

    def _partition_course_enrollments_by_audit(self, enterprise_course_enrollments):
        """
        Partition active enterprise course enrollments into audit and non-audit.

        Arguments:
            enterprise_enrollments: List of tuples containing course_id and whether enrollment is audit.

        Returns:
            Tuple of two lists containing course ids: (enrolled_non_audit, enrolled_audit)
        """
        enrolled_non_audit = []
        enrolled_audit = []
        for enrollment in enterprise_course_enrollments:
            (enrolled_audit if enrollment.is_audit_enrollment else enrolled_non_audit).append(enrollment)
        return enrolled_non_audit, enrolled_audit

    def _get_audit_modes(self):
        """
        Get the configured audit modes from settings.
        """
        return getattr(settings, 'ENTERPRISE_COURSE_ENROLLMENT_AUDIT_MODES', ['audit', 'honor'])

    def _partition_default_enrollment_intentions_by_enrollment_status(
        self,
        default_enrollment_intentions,
        enrolled_non_audit,
        enrolled_audit,
    ):
        """
        Partition default enrollment intentions into enrollable and non-enrollable.

        Arguments:
            default_enrollment_intentiosn: List of default enrollment intentions.
            enrolled_non_audit: List of course runs in which the learner is enrolled in non-audit mode.
            enrolled_audit: List of course runs in which the learner is enrolled in audit mode.

        Returns:
            Tuple of three lists: (already_enrolled, needs_enrollment_enrollable, needs_enrollment_not_enrollable)
        """
        already_enrolled = []
        needs_enrollment_enrollable = []
        needs_enrollment_not_enrollable = []

        non_audit_enrollments_dict = {enrollment.course_id: enrollment for enrollment in enrolled_non_audit}
        audit_enrollments_dict = {enrollment.course_id: enrollment for enrollment in enrolled_audit}

        for intention in default_enrollment_intentions:
            has_applicable_catalogs = intention.applicable_enterprise_catalog_uuids
            non_audit_enrollment = non_audit_enrollments_dict.get(intention.course_run_key, None)
            audit_enrollment = audit_enrollments_dict.get(intention.course_run_key, None)

            if non_audit_enrollment and non_audit_enrollment.is_active:
                # Learner is already enrolled (is_active=True) in non-audit mode for this course run
                already_enrolled.append((intention, non_audit_enrollment))
                continue

            if non_audit_enrollment and non_audit_enrollment.unenrolled:
                # Learner has un-enrolled in non-audit mode for this course run,
                # so don't consider this as an enrollable intention.
                # Note that that we don't consider the case of an unenrolled *audit* enrollment,
                # because default enrollments should be "exactly once" per (user, enterprise), if possible.
                # If only an (unenrolled) audit enrollment exists, it means the user likely
                # never had a default intention realized for them in the given course,
                # so we'd still like to consider it as enrollable.
                needs_enrollment_not_enrollable.append((intention, non_audit_enrollment))
                continue

            if not intention.is_course_run_enrollable:
                # Course run is not enrollable
                needs_enrollment_not_enrollable.append((intention, audit_enrollment))
                continue

            has_non_audit_mode_for_course_run = intention.best_mode_for_course_run not in self._get_audit_modes()
            is_audit_enrollment_with_non_audit_modes = audit_enrollment and has_non_audit_mode_for_course_run

            # NOTE: The order of the following conditions is crucial for correctly categorizing
            # default enrollment intentions based on the learner's enrollment state. Changing the
            # order may result in incorrect handling of different enrollment scenarios, such as
            # unenrolled vs. enrolled states (audit vs. verified). If you need to modify the order,
            # ensure you understand, verify, and test the changes.
            if is_audit_enrollment_with_non_audit_modes and has_applicable_catalogs:
                # Learner is enrolled in this course run in audit, there exists a non-audit mode, and
                # there are applicable catalogs for potential upgrade to paid mode.
                needs_enrollment_enrollable.append((intention, audit_enrollment))
            elif is_audit_enrollment_with_non_audit_modes and not has_applicable_catalogs:
                # Learner is enrolled in this course run in audit, there exists a non-audit mode, but
                # there are no applicable catalogs.
                needs_enrollment_not_enrollable.append((intention, audit_enrollment))
            elif audit_enrollment and audit_enrollment.is_active and not has_non_audit_mode_for_course_run:
                # Learner is enrolled in this course run in audit, there are no non-audit modes. As such,
                # there's no potential upgrade needed and should be considered already enrolled.
                already_enrolled.append((intention, audit_enrollment))
            elif not has_applicable_catalogs:
                # Learner is not enrolled in this course run, audit or otherwise; though enrollment is needed
                # there are no applicable catalogs containing the course run (not enrollable).
                needs_enrollment_not_enrollable.append((intention, non_audit_enrollment or audit_enrollment))
            else:
                # Learner is not yet enrolled in this course run, audit or otherwise; enrollment is needed (enrollable).
                needs_enrollment_enrollable.append((intention, non_audit_enrollment or audit_enrollment))

        return already_enrolled, needs_enrollment_enrollable, needs_enrollment_not_enrollable

    def _get_serializer_context_for_learner_status(
        self,
        default_enrollment_intentions_for_customer,
        enterprise_course_enrollments_for_learner,
    ):
        """
        Get the serializer context for learner status, grouping the default enrollment intentions
        based on the learner's enrollment status and whether the course run is currently enrollable.
        """
        enrolled_non_audit, enrolled_audit = self._partition_course_enrollments_by_audit(
            enterprise_course_enrollments_for_learner
        )
        already_enrolled, needs_enrollment_enrollable, needs_enrollment_not_enrollable = (
            self._partition_default_enrollment_intentions_by_enrollment_status(
                default_enrollment_intentions_for_customer,
                enrolled_non_audit,
                enrolled_audit,
            )
        )
        return {
            'needs_enrollment': {
                'enrollable': needs_enrollment_enrollable,
                'not_enrollable': needs_enrollment_not_enrollable,
            },
            'already_enrolled': already_enrolled,
        }
