# -*- coding: utf-8 -*-
"""
Django signal handlers.
"""

from logging import getLogger

from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from enterprise import roles_api
from enterprise.api import activate_admin_permissions
from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient
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
)
from enterprise.tasks import create_enterprise_enrollment
from enterprise.utils import (
    NotConnectedToOpenEdX,
    delete_tableau_user_by_id,
    get_default_catalog_content_filter,
    unset_enterprise_learner_language,
    unset_language_of_all_enterprise_learners,
)

try:
    from common.djangoapps.student.models import CourseEnrollment
except ImportError:
    CourseEnrollment = None

logger = getLogger(__name__)
_UNSAVED_FILEFIELD = 'unsaved_filefield'


@disable_for_loaddata
def handle_user_post_save(sender, **kwargs):  # pylint: disable=unused-argument
    """
    Handle User model changes. Context: This signal runs any time a user logs in, including b2c users.

    Steps:
    1. Check for existing PendingEnterpriseCustomerUser(s) for user's email. If one or more
        exists, create an EnterpriseCustomerUser record for each which will ensure the user
        has the "enterprise_learner" role.
    2. When we get a new EnterpriseCustomerUser record (or an existing record if one existed), check if the
        PendingEnterpriseCustomerUser has any pending course enrollments. If so, enroll the user in these courses.
    3. Delete the PendingEnterpriseCustomerUser record as its no longer needed.
    4. Using the newly created EnterpriseCustomerUser (or an existing record if one existed), check if there
        is a PendingEnterpriseCustomerAdminUser. If so, ensure the user has the "enterprise_admin" role and
        a Tableau user is created for the user.
    """
    created = kwargs.get("created", False)
    user_instance = kwargs.get("instance", None)

    if user_instance is None:
        return  # should never happen, but better safe than 500 error

    pending_ecus = PendingEnterpriseCustomerUser.objects.filter(user_email=user_instance.email)

    # link PendingEnterpriseCustomerUser to the EnterpriseCustomer and fulfill pending enrollments
    for pending_ecu in pending_ecus:
        enterprise_customer_user = pending_ecu.link_pending_enterprise_user(
            user=user_instance,
            is_user_created=created,
        )
        pending_ecu.fulfill_pending_course_enrollments(enterprise_customer_user)
        pending_ecu.delete()

    enterprise_customer_users = EnterpriseCustomerUser.objects.filter(user_id=user_instance.id)
    for enterprise_customer_user in enterprise_customer_users:
        # activate admin permissions for an existing EnterpriseCustomerUser(s), if applicable
        activate_admin_permissions(enterprise_customer_user)


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


@receiver(post_delete, sender=EnterpriseCustomerUser)
def delete_enterprise_admin_role_assignment(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Delete the associated enterprise admin role assignment record when deleting an EnterpriseCustomerUser record.
    """
    if instance.user:
        roles_api.delete_admin_role_assignment(
            user=instance.user,
            enterprise_customer=instance.enterprise_customer,
        )


@receiver(post_save, sender=EnterpriseCustomerUser)
def assign_or_delete_enterprise_learner_role(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Assign or delete enterprise_learner role for EnterpriseCustomerUser when updated.

    The enterprise_learner role is assigned when a new EnterpriseCustomerUser record is
    initially created and removed when a EnterpriseCustomerUser record is updated and
    unlinked (i.e., soft delete - see ENT-2538).
    """
    if not instance.user:
        return

    if kwargs['created']:
        roles_api.assign_learner_role(
            instance.user,
            enterprise_customer=instance.enterprise_customer,
        )
    elif not kwargs['created']:
        # EnterpriseCustomerUser record was updated
        if instance.linked:
            roles_api.assign_learner_role(
                instance.user,
                enterprise_customer=instance.enterprise_customer,
            )
        else:
            roles_api.delete_learner_role_assignment(
                user=instance.user,
                enterprise_customer=instance.enterprise_customer,
            )


@receiver(post_delete, sender=EnterpriseCustomerUser)
def delete_enterprise_learner_role_assignment(sender, instance, **kwargs):     # pylint: disable=unused-argument
    """
    Delete the associated enterprise learner role assignment record when deleting an EnterpriseCustomerUser record.
    """
    if not instance.user:
        return

    roles_api.delete_learner_role_assignment(
        user=instance.user,
        enterprise_customer=instance.enterprise_customer,
    )


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
    Delete the associated enterprise analytics user in Tableau.
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
    catalogs = instance.enterprise_customer_catalogs.all()

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

    Additionally sends a request to update the catalog's metadata from discovery, and index any relevant content for
    Algolia.
    """
    catalog_uuid = instance.uuid
    catalog_query_uuid = str(instance.enterprise_catalog_query.uuid) if instance.enterprise_catalog_query else None
    query_title = getattr(instance.enterprise_catalog_query, 'title', None) \
        if instance.enterprise_catalog_query else None
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
                catalog_query_uuid,
                query_title,
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
                'catalog_query_uuid': catalog_query_uuid,
                'query_title': query_title,
            }
            catalog_client.update_enterprise_catalog(catalog_uuid, **update_fields)
        # Refresh catalog on all creates and updates
        catalog_client.refresh_catalogs([instance])


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
        ecu = EnterpriseCustomerUser.objects.filter(user_id=user_id, active=True).first()
        if not ecu:
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
