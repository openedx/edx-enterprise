# -*- coding: utf-8 -*-
"""
Mixins for edX Enterprise's Consent application.
"""

from django.contrib.auth.models import User
from django.utils.encoding import python_2_unicode_compatible

from enterprise.models import EnterpriseCourseEnrollment


@python_2_unicode_compatible
class ConsentModelMixin:
    """
    A mixin for Data Sharing Consent classes that require common, reusable functionality.
    """

    def __str__(self):
        """
        Return a human-readable string representation.
        """
        return "<{class_name} for user {username} of Enterprise {enterprise_name}>".format(
            class_name=self.__class__.__name__,
            username=self.username,
            enterprise_name=self.enterprise_customer.name,
        )

    def __repr__(self):
        """
        Return a uniquely identifying string representation.
        """
        return self.__str__()

    def consent_required(self):
        """
        Return a boolean value indicating whether a consent action must be taken.
        """
        children = getattr(self, '_child_consents', [])
        if children:
            return any((child.consent_required() for child in children))

        if self.granted:
            return False

        return bool(
            (self.enterprise_customer.enforces_data_sharing_consent('at_enrollment')) and
            (self.enterprise_customer.catalog_contains_course(self.course_id))
        )

    @property
    def enterprise_enrollment_exists(self):
        """
        Determine whether there exists an EnterpriseCourseEnrollment related to this consent record.
        """
        if self.course_id:
            try:
                user_id = User.objects.get(username=self.username).pk
            except User.DoesNotExist:
                return False
            return EnterpriseCourseEnrollment.objects.filter(
                course_id=self.course_id,
                enterprise_customer_user__user_id=user_id,
                enterprise_customer_user__enterprise_customer=self.enterprise_customer,
            ).exists()
        return False

    @property
    def exists(self):
        """
        Determine whether a record related to the consent scenario exists.

        First, check the instance's own `_exists` attribute; this is set to True
        on database-backed instances that have a primary key, and may be manually
        set to true on ProxyDataSharingConsent objects that have database-backed
        children. If unsuccessful, check to see if an EnterpriseCourseEnrollment
        related to this consent record exists; we treat that as though this record
        exists for the purposes of serializable API responses.

        We want to check for EnterpriseCourseEnrollment records because there are
        cases where one will be created, but not the other. In particular, proxy
        enrollments create an ECE but not any consent record. The LMS uses the
        API's 'exists' key to determine if consent action should be taken for course
        enrollments that have prior existence but for which consent has not been
        granted. Thus, 'exists' is used as a proxy for the question "has any workflow
        been entered which may involve a necessity for the learner to grant consent?"
        """
        return self._exists or self.enterprise_enrollment_exists

    def serialize(self):
        """
        Return a dictionary that provides the core details of the consent record.
        """
        details = {
            'username': self.username,
            'enterprise_customer_uuid': self.enterprise_customer.uuid,
            'exists': self.exists,
            'consent_provided': self.granted,
            'consent_required': self.consent_required(),
        }
        if self.course_id:
            details['course_id'] = self.course_id
        if getattr(self, 'program_uuid', None):
            details['program_uuid'] = self.program_uuid
        return details
