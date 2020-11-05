# -*- coding: utf-8 -*-
"""
Django signal handlers.
"""

from logging import getLogger

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
from enterprise.constants import ENTERPRISE_ADMIN_ROLE, ENTERPRISE_LEARNER_ROLE
from enterprise.decorators import disable_for_loaddata
from enterprise.models import (
    EnterpriseAnalyticsUser,
    EnterpriseCatalogQuery,
    EnterpriseCustomer,
    EnterpriseCustomerBrandingConfiguration,
    EnterpriseCustomerCatalog,
    EnterpriseCustomerUser,
    PendingEnterpriseCustomerAdminUser,
    PendingEnterpriseCustomerUser,
    SystemWideEnterpriseRole,
    SystemWideEnterpriseUserRoleAssignment,
)
from enterprise.tasks import create_enterprise_enrollment
from enterprise.utils import (
    NotConnectedToOpenEdX,
    create_tableau_user,
    delete_tableau_user_by_id,
    get_default_catalog_content_filter,
    track_enrollment,
    unset_enterprise_learner_language,
    unset_language_of_all_enterprise_learners,
)

try:
    from student.models import CourseEnrollment
except ImportError:
    CourseEnrollment = None

logger = getLogger(__name__)  # pylint: disable=invalid-name
_UNSAVED_FILEFIELD = 'unsaved_filefield'


@disable_for_loaddata
def handle_user_post_save(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Handle User model changes - checks if pending enterprise customer user record exists and upgrades it to actual link.

    If there are pending enrollments attached to the PendingEnterpriseCustomerUser, then this signal also takes the
    newly-created users and enrolls them in the relevant courses.
    """
    created = kwargs.get("created", False)
    user_instance = kwargs.get("instance", None)

    if user_instance is None:
        return  # should never happen, but better safe than 500 error

    try:
        pending_ecu = PendingEnterpriseCustomerUser.objects.get(user_email=user_instance.email)
    except PendingEnterpriseCustomerUser.DoesNotExist:
        return  # nothing to do in this case

    if not created:
        # existing user changed his email to match one of pending link records - try linking him to EC
        try:
            existing_record = EnterpriseCustomerUser.objects.get(user_id=user_instance.id)
            message_template = "User {user} have changed email to match pending Enterprise Customer link, " \
                               "but was already linked to Enterprise Customer {enterprise_customer} - " \
                               "deleting pending link record"
            logger.info(message_template.format(
                user=user_instance, enterprise_customer=existing_record.enterprise_customer
            ))
            pending_ecu.delete()
            return
        except EnterpriseCustomerUser.DoesNotExist:
            pass  # everything ok - current user is not linked to other ECs

    enterprise_customer_user = EnterpriseCustomerUser.objects.create(
        enterprise_customer=pending_ecu.enterprise_customer,
        user_id=user_instance.id
    )
    pending_enrollments = list(pending_ecu.pendingenrollment_set.all())
    if pending_enrollments:
        def _complete_user_enrollment():
            """
            Complete an Enterprise User's enrollment.

            EnterpriseCustomers may enroll users in courses before the users themselves
            actually exist in the system; in such a case, the enrollment for each such
            course is finalized when the user registers with the OpenEdX platform.
            """
            for enrollment in pending_enrollments:
                enterprise_customer_user.enroll(
                    enrollment.course_id,
                    enrollment.course_mode,
                    cohort=enrollment.cohort_name,
                    source_slug=getattr(enrollment.source, 'slug', None),
                    discount_percentage=enrollment.discount_percentage,
                    sales_force_id=enrollment.sales_force_id,
                )
                track_enrollment('pending-admin-enrollment', user_instance.id, enrollment.course_id)
            pending_ecu.delete()
        transaction.on_commit(_complete_user_enrollment)
    else:
        pending_ecu.delete()


@receiver(pre_save, sender=EnterpriseCustomer)
def update_lang_pref_of_all_learners(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Update the language preference of all the learners belonging to the enterprise customer.
    Set the language preference to the value enterprise customer has used as the `default_language`.
    """
    # Unset the language preference when a new learner is linked with the enterprise customer.
    # The middleware in the enterprise will handle the cases for setting a proper language for the learner.
    if instance.default_language:
        prev_state = EnterpriseCustomer.objects.filter(uuid=instance.uuid).first()
        if prev_state is None or prev_state.default_language != instance.default_language:
            # Unset the language preference of all the learners linked with the enterprise customer.
            # The middleware in the enterprise will handle the cases for setting a proper language for the learner.
            unset_language_of_all_enterprise_learners(instance)


@receiver(pre_save, sender=EnterpriseCustomerBrandingConfiguration)
def skip_saving_logo_file(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    To avoid saving the logo image at an incorrect path, skip saving it.
    """
    if not instance.id and not hasattr(instance, _UNSAVED_FILEFIELD):
        setattr(instance, _UNSAVED_FILEFIELD, instance.logo)
        instance.logo = None


@receiver(post_save, sender=EnterpriseCustomerBrandingConfiguration)
def save_logo_file(sender, instance, **kwargs):            # pylint: disable=unused-argument
    """
    Now that the object is instantiated and instance.id exists, save the image at correct path and re-save the model.
    """
    if kwargs['created'] and hasattr(instance, _UNSAVED_FILEFIELD):
        instance.logo = getattr(instance, _UNSAVED_FILEFIELD)
        delattr(instance, _UNSAVED_FILEFIELD)
        instance.save()


@receiver(post_save, sender=EnterpriseCustomerCatalog, dispatch_uid='default_content_filter')
def default_content_filter(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Set default value for `EnterpriseCustomerCatalog.content_filter` if not already set.
    """
    if kwargs['created'] and not instance.content_filter:
        instance.content_filter = get_default_catalog_content_filter()
        instance.save()


@receiver(post_save, sender=EnterpriseCustomerUser)
def assign_or_delete_enterprise_admin_role(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Assign or delete enterprise_admin role for EnterpriseCustomerUser when updated.
    Create third party analytics user.

    This only occurs if a PendingEnterpriseCustomerAdminUser record exists.
    """
    if instance.user:
        enterprise_admin_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_ADMIN_ROLE)
        try:
            pending_enterprise_admin_user = PendingEnterpriseCustomerAdminUser.objects.get(
                user_email=instance.user.email,
                enterprise_customer=instance.enterprise_customer,
            )
        except PendingEnterpriseCustomerAdminUser.DoesNotExist:
            pending_enterprise_admin_user = None

        if kwargs['created'] and pending_enterprise_admin_user:
            # EnterpriseCustomerUser record was created and a pending admin user
            # exists, so assign the enterprise_admin role.
            pending_enterprise_admin_user.activate_admin_permissions(
                user=instance.user,
                enterprise_customer=instance.enterprise_customer,
            )
            # Also create the Enterprise admin user in third party analytics application with the enterprise
            # customer uuid as username.
            tableau_username = str(instance.enterprise_customer.uuid).replace('-', '')
            create_tableau_user(tableau_username, instance)
        elif not kwargs['created'] and not instance.linked:
            # EnterpriseCustomerUser record was updated but is not linked, so delete the enterprise_admin role.
            try:
                SystemWideEnterpriseUserRoleAssignment.objects.get(
                    user=instance.user,
                    role=enterprise_admin_role
                ).delete()
            except SystemWideEnterpriseUserRoleAssignment.DoesNotExist:
                # Do nothing if no role assignment is present for the enterprise customer user.
                pass
        else:
            logger.info(
                'Could not assign or delete enterprise_admin role for user %s'
                ' due to a PendingEnterpriseCustomerAdminUser record not existing'
                ' or the user not being linked.',
                instance.user.id,
            )


@receiver(post_delete, sender=EnterpriseCustomerUser)
def delete_enterprise_admin_role_assignment(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Delete the associated enterprise admin role assignment record when deleting an EnterpriseCustomerUser record.
    """
    if instance.user:
        enterprise_admin_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_ADMIN_ROLE)
        SystemWideEnterpriseUserRoleAssignment.objects.filter(
            user=instance.user,
            role=enterprise_admin_role
        ).delete()


@receiver(post_save, sender=EnterpriseCustomerUser)
def assign_or_delete_enterprise_learner_role(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Assign or delete enterprise_learner role for EnterpriseCustomerUser when updated.

    The enterprise_learner role is assigned when a new EnterpriseCustomerUser record is
    initially created and removed when a EnterpriseCustomerUser record is updated and
    unlinked (i.e., soft delete - see ENT-2538).
    """
    if instance.user:
        enterprise_learner_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_LEARNER_ROLE)
        if kwargs['created']:
            # EnterpriseCustomerUser record was created, so assign the enterprise_learner role
            SystemWideEnterpriseUserRoleAssignment.objects.get_or_create(
                user=instance.user,
                role=enterprise_learner_role
            )
        elif not kwargs['created'] and not instance.linked:
            # EnterpriseCustomerUser record was updated but is not linked, so delete the enterprise_learner role
            try:
                SystemWideEnterpriseUserRoleAssignment.objects.get(
                    user=instance.user,
                    role=enterprise_learner_role
                ).delete()
            except SystemWideEnterpriseUserRoleAssignment.DoesNotExist:
                # Do nothing if no role assignment is present for the enterprise customer user.
                pass


@receiver(post_delete, sender=EnterpriseCustomerUser)
def delete_enterprise_learner_role_assignment(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Delete the associated enterprise learner role assignment record when deleting an EnterpriseCustomerUser record.
    """
    if instance.user:
        enterprise_learner_role, __ = SystemWideEnterpriseRole.objects.get_or_create(name=ENTERPRISE_LEARNER_ROLE)
        try:
            SystemWideEnterpriseUserRoleAssignment.objects.get(
                user=instance.user,
                role=enterprise_learner_role
            ).delete()
        except SystemWideEnterpriseUserRoleAssignment.DoesNotExist:
            # Do nothing if no role assignment is present for the enterprise customer user.
            pass


@receiver(post_save, sender=EnterpriseCustomerUser)
def update_learner_language_preference(sender, instance, created, **kwargs):     # pylint: disable=unused-argument
    """
    Update the language preference of the learner.
    Set the language preference to the value enterprise customer has used as the `default_language`.
    """
    # Unset the language preference when a new learner is linked with the enterprise customer.
    # The middleware in the enterprise will handle the cases for setting a proper language for the learner.
    if created and instance.enterprise_customer.default_language:
        unset_enterprise_learner_language(instance)


@receiver(pre_delete, sender=EnterpriseAnalyticsUser)
def delete_enterprise_analytics_user(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Delete the associated enterprise analytics user in tableau.
    """
    if instance.analytics_user_id:
        delete_tableau_user_by_id(instance.analytics_user_id)


@receiver(post_save, sender=PendingEnterpriseCustomerAdminUser)
def create_pending_enterprise_admin_user(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Creates a PendingEnterpriseCustomerUser when a PendingEnterpriseCustomerAdminUser is created.
    """
    PendingEnterpriseCustomerUser.objects.get_or_create(
        enterprise_customer=instance.enterprise_customer,
        user_email=instance.user_email,
    )


@receiver(post_delete, sender=PendingEnterpriseCustomerAdminUser)
def delete_pending_enterprise_admin_user(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Deletes a PendingEnterpriseCustomerUser when its associated PendingEnterpriseCustomerAdminUser is removed.
    """
    PendingEnterpriseCustomerUser.objects.filter(
        enterprise_customer=instance.enterprise_customer,
        user_email=instance.user_email,
    ).delete()


@receiver(post_save, sender=EnterpriseCatalogQuery)
def update_enterprise_catalog_query(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Sync data changes from Enterprise Catalog Query to the Enterprise Customer Catalog.
    """
    updated_content_filter = instance.content_filter
    logger.info(
        'Running update_enterprise_catalog_query for Catalog Query {} with updated_content_filter {}'.format(
            instance.pk,
            updated_content_filter
        )
    )
    catalogs = instance.enterprise_customer_catalogs.filter(sync_enterprise_catalog_query=True)

    for catalog in catalogs:
        logger.info(
            'update_enterprise_catalog_query is updating catalog {} with the updated_content_filter.'.format(
                catalog.uuid
            )
        )
        catalog.content_filter = updated_content_filter
        catalog.save()


@receiver(post_save, sender=EnterpriseCustomerCatalog)
def update_enterprise_catalog_data(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Send data changes to Enterprise Catalogs to the Enterprise Catalog Service.
    """
    catalog_uuid = instance.uuid
    try:
        catalog_client = EnterpriseCatalogApiClient()
        if kwargs['created']:
            response = catalog_client.get_enterprise_catalog(
                catalog_uuid=catalog_uuid,
                # Suppress 404 exception on create since we do not expect the catalog
                # to exist yet in enterprise-catalog
                should_raise_exception=False,
            )
        else:
            response = catalog_client.get_enterprise_catalog(catalog_uuid=catalog_uuid)
    except NotConnectedToOpenEdX as exc:
        logger.exception(
            'Unable to update Enterprise Catalog {}'.format(str(catalog_uuid)), exc_info=exc
        )
    else:
        if not response:
            # catalog with matching uuid does NOT exist in enterprise-catalog
            # service, so we should create a new catalog
            catalog_client.create_enterprise_catalog(
                str(catalog_uuid),
                str(instance.enterprise_customer.uuid),
                instance.enterprise_customer.name,
                instance.title,
                instance.content_filter,
                instance.enabled_course_modes,
                instance.publish_audit_enrollment_urls,
            )
        else:
            # catalog with matching uuid does exist in enterprise-catalog
            # service, so we should update the existing catalog
            update_fields = {
                'enterprise_customer': str(instance.enterprise_customer.uuid),
                'enterprise_customer_name': instance.enterprise_customer.name,
                'title': instance.title,
                'content_filter': instance.content_filter,
                'enabled_course_modes': instance.enabled_course_modes,
                'publish_audit_enrollment_urls': instance.publish_audit_enrollment_urls,
            }
            catalog_client.update_enterprise_catalog(catalog_uuid, **update_fields)


@receiver(post_delete, sender=EnterpriseCustomerCatalog)
def delete_enterprise_catalog_data(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Send deletions of Enterprise Catalogs to the Enterprise Catalog Service.
    """
    catalog_uuid = instance.uuid
    try:
        catalog_client = EnterpriseCatalogApiClient()
        catalog_client.delete_enterprise_catalog(catalog_uuid)
    except NotConnectedToOpenEdX as exc:
        logger.exception(
            'Unable to delete Enterprise Catalog {}'.format(str(catalog_uuid)),
            exc_info=exc
        )


def create_enterprise_enrollment_receiver(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Watches for post_save signal for creates on the CourseEnrollment table.

    Spin off an async task to generate an EnterpriseCourseEnrollment if appropriate.
    """
    if kwargs.get('created') and instance.user:
        user_id = instance.user.id
        try:
            ecu = EnterpriseCustomerUser.objects.get(user_id=user_id)
        except ObjectDoesNotExist:
            return
        logger.info((
            "User %s is an EnterpriseCustomerUser. "
            "Spinning off task to check if course is within User's "
            "Enterprise's EnterpriseCustomerCatalog."
        ), user_id)

        create_enterprise_enrollment.delay(
            str(instance.course_id),
            ecu.id,
        )


# Don't connect this receiver if we dont have access to CourseEnrollment model
if CourseEnrollment is not None:
    post_save.connect(create_enterprise_enrollment_receiver, sender=CourseEnrollment)
