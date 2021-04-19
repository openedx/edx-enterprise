Change Log
==========

..
   All enhancements and patches to edx-enterprise will be documented
   in this file.  It adheres to the structure of http://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description). Additionally, we no longer
   track the date here since PyPi has its own history of dates based on when
   the package is published.

   This project adheres to Semantic Versioning (http://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
----------
* Nothing.

[3.22.8]
--------
* Add dashboard admin rbac role permission on tableau auth view so that only
  enterprise dashboard admins can access this view.
* Add support to generate tableau auth token based on incoming enterprise customer's uuid

[3.22.7]
--------
* chore: upgrade edx-enterprise requirements

[3.22.6]
--------
* Improves performance of enterprise role assignment admin page
* Deletes custom get_search_results() method, since ``enterprise_customer__name`` is now a viable search field
* Improves pagination by asking for an estimated row count from Mysql ``INFORMATION_SCHEMA.TABLES``
* Turns 1 + N query into 1 query via proper use of ``list_select_related``

[3.22.5]
--------
* Fix: no longer stringifying `None` values passed to enterprise catalog creations calls

[3.22.4]
--------
* Fix: learner_data exporter bug fix and refactor for cleaner enrollment filtering

[3.22.3]
--------
* Feature: including EnterpriseCatalogQuery UUID field in request payload to enterprise-catalog on EnterpriseCatalog updates

[3.22.2]
--------
* Feature: new UUID field on EnterpriseCatalogQuery model (and update to all existing query objects)

[3.22.1]
--------
* Refactor: integrated channels learner exporter replace course api client

[3.22.0]
--------
* Added a management command to send emails to learners with missing DSC

[3.21.4]
--------
* allow searching of enterprise customer records with hyphenated uuid
* add typeahead search dropdown to imporve enterprise customer search on
  enterprise reporting configuration

[3.21.3]
--------
* When a learner is linked from manage learners page, in-activate learner's other enterprises

[3.21.2]
--------
* Added support of multiple identity_providers in enterprise.models.get_remote_id.

[3.21.1]
--------
* Added multiple identity_providers in EnterpriseCustomerApi

[3.21.0]
--------
* Added the ability to link/unlink enterprise customer catalogs with enterprise reporting configuration via its API endpoint.

[3.20.5]
--------
* Integrated channels learner_data module refactored to avoid making some LMS REST API calls

[3.20.4]
--------
* Refactored code in `proxied_get()` to clean up duplicate logic.

[3.20.3]
--------

* Removing unused and out of date endpoints for Bulk Enrollment

[3.20.2]
--------
* Allow licensed audit enrollment to have a path to upgrade into verified

[3.20.1]
--------
* update edx-rbac to 1.4.2, plus a bunch of other version bumps.

[3.20.0]
--------
* feat: add support for enterprise admins to create pending enterprise users

[3.19.0]
--------
* feat: add support for creating multiple pending enterprise users

[3.18.7]
--------

* Refactored bulk enrollment serializer and bug fixes to the bulk enrollment endpoint.

[3.18.6]
--------

* fix: The update_role_assignments_with_customers command no longer updates records.  It only creates
  new records, which helps de-risk the operation.

[3.18.5]
--------
* fix: do not include unpublished courses when enrollment link resolves course_runs

[3.18.4]
--------

* fix: The update_role_assignments_with_customers command no longer deletes open assignments.  Allowing it to do so
  left us prone to error when an explicit enterprise_customer_uuid arg is provided.  We should modify this command
  in the future to perform deletions of open assignments as its only action, and it should only be invoked this way
  after we have verified that all backfilled enterprise_customer fields on the assignments have been set correctly.

[3.18.3]
--------

* Adds the catalog admin role to ``roles_api.roles_by_name()``.

[3.18.2]
--------

* Removes course mode as a required parameter to the bulk subscription enrollment endpoint.

[3.18.1]
--------

* Adds bulk enterprise learner in bulk courses enrollment endpoint with pending user support.

[3.18.0]
--------

* Adds a management command to update all ``SystemWideEnterpriseUserRoleAssignment`` records in a way
  that makes them more explicitly defined.

[3.17.47]
---------

* Bug fix to remove a deprecated parameter that was causing bulk enrollments to fail.

[3.17.46]
---------

* Made help text of sender_alias more generic.

[3.17.45]
---------

* Fix bulk enrollment endpoint to process email_csv and email as well

[3.17.44]
---------

* Replaced an LMS Enrollment API call with direct call the DB to avoid LMS rate limiting during integrated channels bulk jobs.

[3.17.43]
---------

* Updated the default IDP priority of enterprises for social auth.

[3.17.42]
---------

* Change canvas_course_id to BigInteger: Integrated Channels

[3.17.41]
---------

* Upgrade django-ipware to version 3.0.2

[3.17.40]
---------

* Read CSV files using `utf-8-sig` encoding to handle Byte Order Mark

[3.17.39]
---------

* Rename `Owners` field to `Partners` for Cornerstone Integration

[3.17.38]

* Omitting assessment level reporting from integrated Canvas learners final grade to not have redundant reported points
  between final grades and subsection grades.

[3.17.37]
---------

* Refactor to only create an ``EnterpriseCourseEnrollment`` if we successfully create/update a ``CourseEnrollment`` record

[3.17.36]
---------

* Properly filtering integrated channels that support assessment level reporting.

[3.17.35]
---------

* Map "estimated_hours" to "credit_hours" in addition to "total_hours" in SAP.

[3.17.34]
---------

* Removing temporary logs from integrated channels.

[3.17.33]
---------

* Enable manually adding learners to multiple enterprises

[3.17.32]
---------

* Adding the logic to select default provider in case an enterprise has multiple identity providers attached.

[3.17.31]
---------

* Change moodle course title in exporter, to include edX text.

[3.17.30]
---------

* Investigatory logging to track down Integrated Channels transmission issues.

[3.17.29]
---------

* Prevent NoneType string concatenation when handling multiple enterprises logistration without redirects.

[3.17.28]
---------

* Adds default field in enterprise customer identity provider table to select default IDP if there are more than one
  IDPs attached with enterprise.

[3.17.27]
---------

* Adding Logging to single learner assessment level reporting task.

[3.17.26]
---------

* Updating docs to reflect method behaviors.

[3.17.25]
---------

* Making failed SAP user remote ID retrievals log relevant context data.

[3.17.24]
---------

* Making sure Canvas Integrated Channel properly url encodes user identifier fields.

[3.17.23]
---------

* Fixing assessment level reporting audit retrieval.

[3.17.22]
---------

* Adds content metadata item transmission table to Django Admin.

[3.17.21]
---------

* Introduce and use a ``roles_api`` module and use the roles API in signal receivers
  that need to create or delete role assignments.
* For created or updated learner and admin enterprise users, associate their user-role
  with the ``enterprise_customer`` to which that user is linked.
* Install django-cache-memoize.

[3.17.20]
---------

* Adds better exception handling to the SAP integrated channels.
* Adds better logging to the base transmission process in the integrated channels.

[3.17.19]
---------

* Removes the sync_enterprise_catalog_query boolean field from the EnterpriseCustomerCatalog model.
* Adds migration to remove the sync_enterprise_catalog_query boolean field.

[3.17.18]
---------

* Removes all references to the sync_enterprise_catalog_query boolean field from the EnterpriseCustomerCatalog model.
* Updates all conditional use of the sync_enterprise_catalog_query field to be True.
* A second PR will follow to remove the model field and perform the db migration (blue/green deployment safe).

[3.17.17]
---------

* Added a catch all exception block to ensure login flow is not interrupted by analytics user sync.

[3.17.16]
---------

* Include course mode for the user's ``student.CourseEnrollment`` in the ``EnterpriseCourseEnrollmentSerializer``.

[3.17.15]
---------

* In ``SystemWideEnterpriseUserRoleAssignment``, Use either ``applies_to_all_contexts`` or ``enterprise_customer``
  if they are True or non-null, respectively, in determining the result of ``get_context()``,
  but continue to return list of all linked enterprise customer UUIDs if not, (which is the current behavior).
  This is a small step on our journey to explicitly defining user-role assignments.

[3.17.14]
---------

* On the ``SystemWideEnterpriseUserRoleAssignment`` model, adds an ``enterprise_customer`` FK (nullable)
  and an ``applies_to_all`` boolean field (defaults to False) that indicates if the user has wildcard permissions.
* Updates the admin to show the "effective" customer in the detail view, and the explicit value in the list view.
  The effective value is the deprecated way we currently determine role assignment -
  by implicitly assigning the role on every customer to which the user is linked.
* In the detail view/form, the "Enterprise customer" dropdown contains only customers
  to which the user is currently linked.

[3.17.13]
---------

* added check to make sure enterprise user can only use linked IdP with their enterprise customer.

[3.17.12]
---------

* Conditionally allows the deletion of individual ``EnterpriseCourseEnrollment`` and related
  ``LicensedEnterpriseCourseEnrollment`` records via the Django Admin site, so that site admins can manually
  delete enterprise enrollments that were created in error.
  This is only allowed if a Django settings feature flag is set to ``True``.

[3.17.11]
---------

* Apply edx-rbac migration to add ``applies_to_all_contexts`` field to ``SystemWideEnterpriseUserRoleAssignment``.
* Added endpoints for Cornerstone integrated channel.

[3.17.10]
---------

* added home page logo for EnterpriseSelectionView and EnterpriseLoginView

[3.17.9]
--------

* Fix deprecation warning: ``third_party_auth`` should be imported as ``common.djangoapps.third_party_auth``.

[3.17.8]
--------

* Added new API endpoints for Degreed integrated channel.

[3.17.7]
--------

* Added new field ``sender_alias`` in enterprise customer which will be used in emails except of default alias.

[3.17.6]
--------

* Non-effectual code cleanup / refactor to remove some final pieces of duplication (canvas, blackboard).

[3.17.5]
--------

* Ensure enterprise course enrollments return valid course run statuses such that when a learner earns a passing certificate, the ``enterprise_course_enrollments`` API endpoint deems the course is complete even though the course itself may not have ended yet per the configured dates.

[3.17.4]
--------

* Add some info to the ``EnterpriseCourseEnrollment`` docstring, add ``is_active`` property to same.

[3.17.3]
--------

* Fixed unnessary integrated channel signal transmission on course completion to inactive customers by adding guard condition.

[3.17.2]
--------

* Stop listening for ``student.CourseEnrollment`` unenrollment signal, as introduced in 3.17.0

[3.17.1]
--------

* Add management command to process expired subscriptions and field on subscriptions to persist that the subscription expiration has been processed

[3.17.0]
--------

* Listen for ``student.CourseEnrollment`` unenrollment signal and delete associated
  ``EnterpriseCourseEnrollment`` record if one exists (we will have a historical record of the deletion).

[3.16.11]
---------

* Retrieve ``EnterpriseCustomerUser`` by both user_id and enterprise_customer to handle users who are pending for more than 1 enterprise.

[3.16.10]
---------

* Forcing embedded enrollment links within integrated Blackboard courses to open new windows to avoid security alert
  prompt.

[3.16.9]
--------

* Upgrade celery to 5.0.4

[3.16.8]
--------

* Added ClientError exception handling for SAPSuccessFactorsAPIClient.

[3.16.7]
--------

* Modify the learner portal enterprise_course_enrollments endpoint to include an ``is_enrollment_active``
  key that indicates the status of the enterprise enrollment's related ``student.CourseEnrollment`.
  Allow the endpoint to optionally accept an ``?is_active`` query param, so that clients may request
  only active enrollments from it.

[3.16.6]
--------

* Improved error handling for SAP Success Factors OAuth2 response.

[3.16.5]
--------

* Refactoring title content metadata in integrated course creation within the Blackboard integrated channel.

[3.16.4]
--------

* Add SuccessFactors Customer Configuration API endpoint.

[3.16.3]
--------

* Update unique constraints for pending Enterprise learners/admins to support users who may be pending for more than 1 Enterprise.
* Fix ``handle_user_post_save`` to account for the potential of being a pending learner/admin for more than 1 Enterprise.

[3.16.2]
--------

* Refactor ``handle_user_post_save`` to be responsible for linking PendingEnterpriseCustomerUser records and granting admin permissions.

[3.16.1]
--------

* Adding backend support for admin portal Blackboard configuration.

[3.16.0]
--------

* Added the ability to enable multiple Identity Providers for a single enterprise customer.

[3.15.0]
--------

* Converted relation between enterprise customer and identity provider to a one-to-many.

[3.14.1]
--------
* Adds new API for Canvas LMS configurations.

[3.14.0]
--------

* Rebranding update: Change fonts and colors, change mobile layout

[3.13.12]
---------

* Adding decorators to missed integrated channel tasks.

[3.13.11]
---------

* Add new API for external LMS configurations.

[3.13.10]
---------

* Use logo from ``get_platform_logo_url`` in the legacy Django templates

[3.13.9]
--------

* Adding Blackboard support for assessment level reporting in the integrated channels.

[3.13.8]
--------

* Bug fix with course key lookup in the Canvas assessment level grade reporting flow.

[3.13.7]
--------

* Rebranding update: move to more robust ``get_platform_logo_url`` and update default branding colors.

[3.13.6]
--------

* Add log for enterprise enrollment page.

[3.13.5]
--------

* Fixed deprecation warnings related with drf methods (detail_route, list_route).

[3.13.4]
--------

* Empty sequence bugfix in catalog api.

[3.13.3]
--------

* Course end date bugfix.

[3.13.2]
--------

* Add course end date to course level metadata.

[3.13.1]
--------

* Base implementation of assessment level reporting for Integrated Channels.

[3.13.0]
--------

* Use full paths for edx-platform/common/djangoapps imports, as described in
  `edx-platform ADR #7 <https://github.com/edx/edx-platform/blob/master/docs/decisions/0007-sys-path-modification-removal.rst>`_.

[3.12.4]
--------

* Fix silent exception in catalog api call.

[3.12.3]
--------

* Add code_owner custom attribute for celery tasks.

[3.12.2]
--------

* Refresh catalog metadata on create and update

[3.12.1]
--------

* added support for grade, completion and course_structure type reports in enterprise report configurations. Added validation to allow these reports for Pearson enterprises only.

[3.12.0]
--------

* Support uploading a ``course_id`` column in the "Manage Learners" CSV bulk upload to allow manual enrollments in multiple courses at once.

[3.11.1]
--------

* Fixes the issue where user preference value can not be null.

[3.11.0]
--------

* Added spanish translations for data sharing consent page.

[3.10.5]
--------

* Update Moodle integration to single transmission to handle responses properly.

[3.10.4]
--------

* Remove hyphens from  enterprise_customer_uuid for admin user creation and tableau authentication.

[3.10.3]
--------

* Fix timout on update.

[3.10.2]
--------

* Updated the logic to clear enterprise learner language in a way that db lock does not happen.

[3.10.1]
--------

* change username with enterprise_customer_uuid for tableau trusted authentication and tableau user creation.

[3.10.0]
--------

* Tests only: upgrade to pytest 6+ and factoryboy 3+ to bring up to date with edx-platform.

[3.9.13]
--------

* Adding Blackboard customization to integrated channel content metadata creation.

[3.9.12]
--------

* change username with user_id for tableau trusted authentication and tableau user creation.

[3.9.11]
--------

* add logs to know if data sharing consent is failing because catalog does not contain the course

[3.9.10]
--------

* added POST enterprise-customer/<uuid>/enterprise_learner endpoint to mimic Manage Learners admin form functionality

[3.9.9]
--------

* upgrade version to create new release on pypi.


[3.9.8]
--------

* added error_codes in the logging/error messages for the CourseEnrollmentView for better debugging capability.

[3.9.7]
--------

* Unset learners language so that default_language from enterprise customer may take effect.

[3.9.6]
--------

* Fix DSC tests to verify enrolling a learner with a license_uuid

[3.9.5]
--------

* ENT-2450: Add action to kick off jobs to refresh enterprise catalogs so changes will be immediately visible

[3.9.4]
--------

* Style/UX changes for Moodle integration.

[3.9.3]
--------

* Adding integrated course customization for Blackboard courses.

[3.9.2]
--------

* Re-add check for license uuid when enrolling learners into a course

[3.9.1]
--------

* Added the EnterpriseAnalyticsUser model and tableau integration functions.

[3.9.0]
--------

* Enable enterprise to have a default language configuration for its learners.

[3.8.43]
--------

* ENT-3557: Improve blackboard view logging to better report root cause of auth failure.

[3.8.42]
--------

* ENT-3460: Adding properties to safely use branding config.

[3.8.41]
--------

* Embedded enterprise in the username was removed for tableau trusted authentication.


[3.8.40]
--------

* Bug fix: SAML stripping for unlinking was not properly removing saml prefix.

[3.8.39]
--------

* Blackboard client update/delete and unit tests.

[3.8.38]
--------

* Reverting changes to EnterpriseCustomerBrandingConfig.

[3.8.37]
--------

* Using python properties for EnterpriseCustomerBrandingConfiguration colors.

[3.8.36]
--------

* Authenticate user with Tableau.

[3.8.35]
--------

* Add default branding config object to the Customer record if null.

[3.8.34]
--------

* Implementing Blackboard completion data tranmission.

[3.8.33]
--------

* During license revocation, if no audit track exists for the course, attempt to unenroll the learer from it.

[3.8.32]
--------

* Catches/Handles error occurring with Moodle integrated channel.

[3.8.31]
--------

* Refactors the revoke endpoint into smaller parts, so that implementing new logic is easier to manage.

[3.8.30]
--------

* Moodle client bug fix

[3.8.29]
--------

* Make email field optional for sftp delivery for enterprise reporting config

[3.8.28]
--------

* Blackboard exporter

[3.8.27]
--------

* Update ``get_service_usernames()`` to read from a list variable (that may not exist).

[3.8.26]
--------

* Moodle completion data implementation

[3.8.25]
--------

* Blackboard client Oauth2 implementation

[3.8.24] 2020-10-02
-------------------

* Allow learners to enroll with their license in courses when DSC is disabled.

[3.8.23] 2020-10-01
-------------------

* Added Audit grade for Audit mode enrollments in integrated channels.

[3.8.22]
--------

* Updated seed_enterprise_devstack_data to enable the test customer's subscription management screen

[3.8.21] 2020-09-28
-------------------

* Add functionality to save logo file at only one location when saving EnterpriseCustomerBrandingConfiguration instance

[3.8.20] 2020-09-24
-------------------

* Better exception handling for integrated channels.

[3.8.19] 2020-09-24
-------------------

* Copy test from edx-platform over to enterprise to test migrations early.

[3.8.18] 2020-09-23
-------------------

* Initial setup for Blackboard Integrated Channel.

[3.8.17] 2020-09-23
-------------------

* Update logo name and path after the instance is saved to replace None with instance id.

[3.8.16] 2020-09-22
-------------------

* Token expiration handling in canvas client.

[3.8.15] 2020-09-22
-------------------

* Update Data Sharing Consent language.

[3.8.14] 2020-09-21
-------------------

* Add Moodle integration to integrated_channels.

[3.8.13] 2020-09-20
-------------------

* Fix issue with canvas channel not finding a course, by using search endpoint

[3.8.12] 2020-09-21
-------------------

* Fix column width issue for DSC and other pages

[3.8.11] 2020-09-18
-------------------

* Upgrading celery version to 4.4.7 for python 3.8 support

[3.8.10] 2020-09-17
-------------------

* Reverting PR #952.

[3.8.9] 2020-09-16
-------------------

* Standardizing log format in integrated channels learner data export.

[3.8.8] 2020-09-15
-------------------

* Fixing the construction of the next param in the proxy login view for SSO.

[3.8.7] 2020-09-15
-------------------

* Adding more informative logs to the integrated channels.

[3.8.6] 2020-09-15
-------------------

* Using viewname in reverse as part of args to prevent IndexOutOfRange exception

[3.8.5] 2020-09-14
-------------------

* Add a field to EnterpriseCustomer to disable main menu navigation for integrated channel customer users.

[3.8.4] 2020-09-14
-------------------

* Add a field for enabling analytics screen in the admin portal for an EnterpriseCustomer.

[3.8.3] 2020-09-14
-------------------

* Add management command to create DSC records.

[3.8.2] 2020-09-11
-------------------

* Course and Course Run enrollment_url now points to learner portal course page if LP enabled.

[3.8.1] 2020-09-10
-------------------

* Canvas channel discovery improvements assorted changes.

[3.8.0] 2020-09-09
-------------------

* Assign "enterprise_admin" system-wide role to pending admin users when registering their user account.

[3.7.8] 2020-09-09
-------------------

* Fixes migration mismatch for Canvas models.

[3.7.7] 2020-09-04
------------------

* The ``seed_enterprise_devstack_data`` management command now accepts an enterprise name when creating an enterprise,
  and the learner portal is activated by default.

[3.7.6] 2020-09-09
-------------------

* Adds the learner data exporter and transmitter to the Canvas integrated channel.

[3.7.5] 2020-09-08
-------------------

* Celery version is now upgraded to latest one

[3.7.4] 2020-09-04
-------------------
* Adds support to capture contract discounts from the Enrollment API by adding ``default_contract_discount``
  to the ``EnterpriseCustomer`` model and passing it to ecommerce when creating orders

[3.7.3] 2020-09-01
-------------------

* Override the ``EnterpriseContentCatalog.save()`` method to sync the ``content_filter`` from an associated
  ``EnterpriseCatalogQuery``, if appropriate.
* Add some logging to the ``update_enterprise_catalog_query`` signal.

[3.7.2] 2020-09-01
-------------------

* The ``seed_enterprise_devstack_data`` management command is now idempotent when creating an enterprise,
  and creates users and operator roles for the license-manager and enterprise-catalog workers.

[3.7.1] 2020-08-28
-------------------

* Also send course image_url to Canvas when creating course.

[3.7.0] 2020-08-27
-------------------

* Fixed Duplicate Calls to OCN API.

[3.6.9] 2020-08-26
-------------------

* Return requested user's linked enterprises only. For staff user return all enterprises.

[3.6.8] 2020-08-26
-------------------

* Added course update and deletion capabilities to the canvas integrated channel.

[3.6.7] 2020-08-26
-------------------

* Changed strings in Manage Learners DSC view.

[3.6.6] 2020-08-24
-------------------

* Added a fix for "Manual Order Not Fulfilled" bug.

[3.6.5] 2020-08-24
-------------------

* Added course mode in ecommerce manual enrollment API.

[3.6.4] 2020-08-18
-------------------

* Canvas transmitter implementation for course creation

[3.6.3] 2020-08-19
-------------------

* Adding Django admin forms for Canvas integration config and cleanup on models.

[3.6.2] 2020-08-17
-------------------

* Adding Canvas integrated channels API endpoint for the oauth process completion

[3.6.1] 2020-08-17
-------------------

* Added logging in enrollment endpoint for test purposes.

[3.6.0] 2020-08-12
-------------------

* ENT-2939: removing waffle flag and utility function used in enterprise-catalog transition


[3.5.4] 2020-08-12
-------------------

* Fixed date format in Cornerstone catalog sync call


[3.5.3] 2020-08-11
-------------------

* Fix permissions issue with license_revoke endpoint in LicensedEnterpriseCourseEnrollmentViewSet.

[3.5.2] 2020-08-11
-------------------

* Add Content Metadata Exporter for Canvas Integration.

[3.5.1] 2020-08-11
-------------------

* Add client instantiation and oauth validation for Canvas integration.

[3.5.0] 2020-08-10
------------------

* Add `update_course_enrollment_mode_for_user` method to the EnrollmentApiClient.
* Create new API endpoint to update the mode for a user's licensed enterprise course enrollments when their enterprise license is revoked.
* Introduce new course run status for `saved_for_later`.
* On revocation of an enterprise license, mark the user's licensed course enrollments as `saved_for_later` and `is_revoked`.

[3.4.40] 2020-08-05
-------------------

* Create fresh migrations from scratch for Canvas since this app is yet to run migrations in platform.

[3.4.39] 2020-08-04
-------------------

* Remove field 'key' from a canvas integrated_channel model (but not migration yet), step 2/3

[3.4.38] 2020-08-04
-------------------

* Migration to remove ``banner_border_color`` and ``banner_background_color`` branding config fields.

[3.4.37] 2020-08-04
-------------------

* Add new field client_id to canvas model for removing older key field (step 1/3)

[3.4.36] 2020-08-04
-------------------

* Remove references to deprecated ``banner_border_color`` and ``banner_background_color`` branding config fields.

[3.4.35] 2020-08-04
-------------------

* Add postman collection for Canvas integrated channel

[3.4.34] 2020-08-03
-------------------

* Migration to copy old color field values to new field.

[3.4.33] 2020-08-03
-------------------

* Add BrandingConfiguration primary/secondary/tertiary color fields.

[3.4.32] 2020-07-31
-------------------

* Add Canvas integrated_channel first cut.

[3.4.31] 2020-07-30
-------------------

* The PendingEnterpriseCustomerUser create action will create an EnterpriseCustomerUser
  if an ``auth.User`` record with the given user_email already exists.

[3.4.30] 2020-07-29
-------------------

* Add flag to sync updates in an EnterpriseCatalogQuery with its associated EnterpriseCustomerCatalogs.
* Create a post_save signal to overwrite the content_filter with the update.
* Changes should also be sent to the Enterprise Catalog service.

[3.4.29] 2020-07-29
-------------------

* Added new view for requesting the DSC for learners for specific course.

[3.4.28] 2020-07-24
-------------------

* Add query params to proxy login redirect for new welcome template to be rendered.
* Fixing proxy_login SSO redirect, adding default next param from proxy_login.

[3.4.27] 2020-07-23
-------------------

* Adds hide_course_original_price field to the serializer for the EnterpriseCustomer endpoint.

[3.4.26] 2020-07-20
-------------------

* Adds proxy login view to allow unauthenticated enterprise learners to login via existing flow from the learner portal.

[3.3.26] 2020-07-17
-------------------

* Uses correct course mode slugs during enrollment from GrantDataSharingPermissions.

[3.3.25] 2020-07-16
-------------------

* Use the GrantDataSharingPermissions view to enroll licensed users in courses

[3.3.24] 2020-07-15
-------------------

* Remove get_due_dates and always return an empty list for due_dates

[3.3.23] 2020-07-13
-------------------

* Remove unnecessary data migration

[3.3.22] 2020-07-13
-------------------

* Final removal of marked_done field

[3.3.21] - 2020-07-10
---------------------

* Gracefully handle when list of subjects for content metadata contains either a list of strings and list of dictionaries


[3.3.20] - 2020-07-09
---------------------
* Added new SAML Config option to EnterpriseCustomer in Django admin.

[3.3.19] - 2020-07-08
---------------------

* Remove database references to marked_done.

[3.3.18] - 2020-07-07
---------------------

* Admin dashboard rules predicates now pass an object into the edx-rbac utility functions.


[3.3.17] - 2020-07-07
---------------------
* Created LicensedEnterpriseCourseEnrollment.


[3.3.16] - 2020-07-02
---------------------

* Change marked_done on EnterpriseCourseEnrollment mode nullable.

[3.3.15] - 2020-06-30
---------------------

* Added health checks for enterprise service.

[3.3.14] - 2020-06-30
---------------------

* Added saved_for_later field to the EnterpriseCourseEnrollment model. This will eventually replace the marked_done field.

[3.3.13] - 2020-06-29
---------------------

* Changed GrantDataSharingPermission to redirect to the intended course instead of dashboard, if consent is not required

[3.3.12] - 2020-06-27
---------------------

* Repair invalid key references in Discovery API Client method.

[3.3.11] - 2020-06-25
---------------------

* Restore EnterpriseCatalogQuery functionality to previous state.

[3.3.10] - 2020-06-24
---------------------

* xAPI: Include course UUID in activity extensions collection

[3.3.9] - 2020-06-24
---------------------

* Remove verbose names from EnterpriseCourseEnrollment model Meta class

[3.3.8] - 2020-06-23
---------------------

* Add support to override enrollment attributes for learners

[3.3.7] - 2020-06-19
---------------------

* Bug fix: Added missing migration for content_filter validation changes.

[3.3.6] - 2020-06-17
---------------------

* Add validation for content_filter subfields in EnterpriseCatalogQuery and EnterpriseCustomerCatalog

[3.3.5] - 2020-06-17
---------------------

* Update processing of marked_done field slightly for cleaner boolean usage in client

[3.3.4] - 2020-06-15
---------------------

* Update GrantDataSharingPermissionView to accept both; course_run_id as well as course_key


[3.3.3] - 2020-06-12
---------------------

* Exclude unpublished course runs when determining available/enrollable status


[3.3.2] - 2020-06-10
---------------------

* Added status key to default content filter for EnterpriseCustomerCatalog.


[3.3.1] - 2020-06-10
---------------------

* Added marked_done field in /enterprise_course_enrollments/ response


[3.3.0] - 2020-06-09
---------------------

* xAPI Integrated Reporting Channel, Version 2


[3.2.22] - 2020-06-09
---------------------

* Added rollback for EnterpriseCourseEnrollment enroll

[3.2.21] - 2020-06-03
---------------------

* Downgrade an error log to a warning to reduce alert noise


[3.2.20] - 2020-06-01
---------------------

* Suppress the 404 exception in get_enterprise_catalog when we expect it
* Add enterprise_customer_uuid to an error message to be more informative
* Delete "enterprise_learner" role assignment when an EnterpriseCustomerUser record is soft deleted (i.e., `linked` attribute is False)
* Update seed_enterprise_devstack_data command to include name on user profiles when creating enterprise users


[3.2.19] - 2020-06-01
---------------------

* Updating the catalog preview URL to use the Catalog Service


[3.2.18] - 2020-05-28
---------------------

* Added the enterprise slug login functionality.


[3.2.17] - 2020-05-27
---------------------

* Improve xAPI enrollment/completion event filtering, transmitting, and recording


[3.2.16] - 2020-05-27
---------------------

* Removing caniusepython3 as it is no longer needed since python3 upgrade.


[3.2.15] - 2020-05-26
---------------------

* Improve EnterpriseRoleAssigment exception messaging


[3.2.14] - 2020-05-19
---------------------

* Converting UUID fields to string for use in can_use_enterprise_catalog


[3.2.13] - 2020-05-15
---------------------

* Added can_use_enterprise_catalog utility function to exclude enterprises from the transition to enterprise-catalog


[3.2.12] - 2020-05-13
---------------------

* Created migration to `update_or_create` a system-wide enterprise role named `enterprise_catalog_admin`


[3.2.11] - 2020-05-12
---------------------

* Moving the post model save logic for Enterprise Catalog to signals.py.


[3.2.10] - 2020-05-08
---------------------

* Updated EnterpriseCustomerCatalogAdmin save hook to check if a corresponding catalog exists in the enterprise-catalog service. If it does, the save hook will update the existing catalog; otherwise, a new catalog will be created.
* Added extra logging when syncing Enterprise Catalog data to the Enterprise Catalog Service.


[3.2.9] - 2020-05-08
--------------------

* Added a flag to enable the slug login for an enterprise customer.


[3.2.8] - 2020-05-07
--------------------

* Makes the data sharing consent template guard against empty/null branding configuration logo values.


[3.2.7] - 2020-05-07
--------------------

* Added extra logging in 'create_enterprise_course_enrollments' management command.


[3.2.6] - 2020-05-06
--------------------

* Added use of traverse_pagination for get_content_metadata in the enterprise_catalog api client.


[3.2.5] - 2020-05-06
--------------------

* Pass enterprise customer's name to enterprise-catalog service during create/update of enterprise catalogs
* Refactor `migrate_enterprise_catalogs` management command to check if a catalog already exists in the enterprise-catalog service. If a catalog already exists, it will be updated with a PUT request; otherwise, a new catalog will be created with a POST request.


[3.2.4] - 2020-05-06
--------------------

* Specified python3.5 version for PyPI release


[3.2.3] - 2020-05-06
--------------------

* Removed support for Django<2.2 & Python3.6
* Added support for python3.8.
* Changes to use catalog query content filter if defined instead of catalog content filter.


[3.2.2] - 2020-05-05
--------------------

* Made enrollment reason optional when linking learners without enrollment.


[3.2.1] - 2020-05-04
--------------------

* Added extra logging in 'create_enterprise_course_enrollments' management command.


[3.2.0] - 2020-04-23
--------------------

* Squashed the sap_success_factors and integrated_channel app migrations.


[3.1.3] - 2020-04-23
--------------------

* Revised "end date" window for determinine course active/inactive status in catalog API responses.


[3.1.2] - 2020-04-21
--------------------

* Added extra exception handling in `create_enterprise_course_enrollments` management command.


[3.1.1] - 2020-04-20
--------------------

* removed get_cache_key and using it from edx-django-utils.


[3.1.0] - 2020-04-14
--------------------

* Squashed the enterprise app migrations.


[3.0.15] - 2020-04-14
---------------------

* Fixed HTML tags bug from short course description in enterprise course enrollment page


[3.0.14] - 2020-04-10
---------------------

* Fixing the traversal of results in get_content_metadata for the enterprise-catalog API client


[3.0.13] - 2020-04-10
---------------------

* Switch catalog_contains_course method to use enterprise catalog service behind waffle sample


[3.0.12] - 2020-04-10
---------------------

* Add USE_ENTERPRISE_CATALOG waffle sample, and remove USE_ENTERPRISE_CATALOG waffle flag
* Switch the use of waffle.flag_is_active to waffle.sample_is_active
* Updates the EnterpriseCatalogApiClient to make the user argument optional. If the user argument is not provided, it will use the "enterprise_worker" user instead
* No longer passes user to the EnterpriseCatalogApiClient during initialization in places where a request and/or user object doesn't already exist


[3.0.11] - 2020-04-10
---------------------

* Fix issue with matching urls for redirect to enterprise selection page


[3.0.10] - 2020-04-08
---------------------

* Use the USE_ENTERPRISE_CATALOG waffle flag for transitioning integrated channels to using the enterprise-catalog service


[3.0.9] - 2020-04-08
--------------------

* Add USE_ENTERPRISE_CATALOG waffle flag
* Switch get_course, get_course_run, get_program, and get_course_and_course_run methods to use enterprise catalog service behind waffle flag


[3.0.8] - 2020-04-08
--------------------

* Converted the EnrollmentApiClient to JWT client.


[3.0.7] - 2020-04-07
--------------------

* Additional xAPI transmission workflow logging


[3.0.6] - 2020-04-06
--------------------

* Added support for bypassing enterprise selection page for enrollment url triggered login


[3.0.5] - 2020-03-31
--------------------

* Added "active" key in enterprise_catalog API for "course" content_type if the "course" has "course_run" available for enrollment.


[3.0.4] - 2020-03-31
--------------------

* Removed the 'EDX_API_KEY' from CourseApiClient.


[3.0.3] - 2020-03-27
--------------------

* Updated enterprise-catalog endpoint urls to match rename

[3.0.2] - 2020-03-26
--------------------

* Improved xApi logging to include statement and LRS endpoint'

[3.0.1] - 2020-03-18
--------------------

* Updated xApi integrated channel to use the updated CourseOverview method 'get_from_ids()'

[3.0.0] - 2020-03-16
--------------------

* Removed use of Bearer Authentication

[2.5.5] - 2020-03-13
--------------------

* Add field for enabling subscription managment screen in the admin portal to EnterpriseCustomer.

[2.5.4] - 2020-03-12
--------------------

* Reset authentication cookies on enterprise selection to update JWT cookie with user's enterprise

[2.5.3] - 2020-03-11
--------------------

* Added the salesforce opportunity_id in manage learner django admin.

[2.5.2] - 2020-03-10
--------------------

* Fixed formatting on JSON fields in django admin forms

[2.5.1] - 2020-03-05
--------------------

* Added new data type for enterprise report configurations

[2.5.0] - 2020-03-03
--------------------

* Removing enterprise_learner_portal_hostname from ent cust model (including api)

[2.4.2] - 2020-02-27
--------------------

* Removed the code for enrolling the program from manage learner django admin panel.

[2.4.1] - 2020-02-26
--------------------

* Update log level from INFO to DEBUG for transmit_content_metadata management command

[2.4.0] - 2020-02-25
--------------------

* Restricted PendingEnterpriseCustomerUser to be linked with only one EnterpriseCustomer at a time

[2.3.9] - 2020-02-17
--------------------

* Added discount percentage support in pending enrollment use case.

[2.3.8] - 2020-02-10
--------------------

* Added totalHours field for successfactors completion event

[2.3.7] - 2020-02-07
--------------------

* Learner attached to multiple enterprises, logging in via SSO should be taken to Enterprise selection page

[2.3.6] - 2020-02-06
--------------------

* Fixed learner data transmission command when grades API return `user_not_enrolled` error

[2.3.4] - 2020-02-04
--------------------

* Remove totalHours field from content metadata export

[2.3.3] - 2020-02-03
--------------------

* Added exception handling for enrollment api calls during manual enrollment

[2.3.2] - 2020-01-31
--------------------

* Adding contact_email to enterprisecustomer admin form

[2.3.1] - 2020-01-29
---------------------

* Updated calls to `manual enrollments api` to include enterprise customer info

[2.3.0] - 2020-01-29
--------------------

* Add soft deletion support for EnterpriseCustomerUser model

[2.2.0] - 2020-01-28
--------------------

* Adding new fields to EnterpriseCustomer and EnterpriseCustomerBrandingConfiguration models

[2.1.7] - 2020-01-28
--------------------

* Revert Edx-Api-Key-replacement-changes

[2.1.6] - 2020-01-27
--------------------

* Updating enterprise catalog migration management command

[2.1.5] - 2020-01-27
--------------------

* Added totalHours field for successfactors export

[2.1.4] - 2020-01-24
--------------------

* add boolean field to track linked/unlinked EnterpriseCustomerUser records

[2.1.03] - 2020-01-24
---------------------

* Code refactor and ability to send learner completion if grade is changed

[2.1.01] - 2020-01-21
---------------------

* Initialized EnrollmentApiClient with enterprise service worker user

[2.1.0] - 2020-01-16
--------------------

* Added hooks to sync EnterpriseCustomerCatalog creation, deletion, and model updates in Django Admin to the new enterprise-catalog service

[2.0.50] - 2020-01-16
---------------------

* Replaced EnrollmentApiClientJwt name back to original client's name.

[2.0.49] - 2020-01-15
---------------------

* Added management command to reset SAPSF completion data.

[2.0.48] - 2020-01-14
---------------------

* Updated enterprise catalog client json formatting.

[2.0.47] - 2020-01-13
---------------------

* Replaced Edx-Api-Key in the remaining endpoints of EnrollmentApiClient

[2.0.46] - 2020-01-10
---------------------

* Introduced management command to migrate enterprise catalog data to new service.

[2.0.45] - 2020-01-09
---------------------

* ENT-2489 | Extracting JSON from discovery service response to calculate size

[2.0.43] - 2020-01-08
---------------------

* Replaced Edx-Api-Key in the ThirdPartyAuthApiClient
* Changed the client in one endpoint of ThirdPartyAuthApiClient
* Endpoint name: model-EnterpriseCustomerUser

[2.0.42] - 2020-01-07
---------------------

* Updated context for user with multiple linked enterprises

[2.0.41] - 2020-01-06
---------------------

* Added enterprise discount percentage in a manual enrollment

[2.0.40] - 2020-01-06
---------------------

* Replaced Edx-Api-Key in the EnrollmentApiClient
* Changed the client in one endpoint of EnrollmentApiClient
* Endpoint name: admin-views-EnterpriseCustomerManageLearnersView

[2.0.39] - 2020-01-06
---------------------

* Replaced Edx-Api-Key in the CourseApiClient
* Changed the client in one endpoint of CourseApiClient
* Endpoint name: exporters-learnerdata

[2.0.38] - 2020-01-02
---------------------

* Changed logging of response size from 2.0.37 (ENT-2489) to use size of response in bytes

[2.0.37] - 2020-01-02
---------------------

* Added logging of response size when requests are made to discovery service for data not in cache

[2.0.36] - 2019-12-30
---------------------

* Use `edx-tincan-py35` PYPI package instead of downloading via git

[2.0.35] - 2019-12-30
---------------------

* Version upgrade for edx-rbac

[2.0.34] - 2019-12-24
---------------------

* Disabled the manual enrollment orders for audit mode enterprise learners.

[2.0.33] - 2019-12-23
---------------------

* Added ability to include or exclude date from the report configuration file name.

[2.0.32] - 2019-12-17
---------------------

* Aligned xAPI statement formats with TinCan/Rustici standards
* While uploading bulk users in 'manager learners' from django admin, better handling if invalid encoding found.

[2.0.31] - 2019-12-11
---------------------

* Added ADR for Multiple User Enterprises.

[2.0.30] - 2019-12-04
---------------------

* Get the enterprise_customer linked with SAML and mark it active.

[2.0.29] - 2019-12-04
---------------------

* Update the enterprise customer in the session in case of customer with multiple linked enterprises

[2.0.28] - 2019-12-3
---------------------

* Added logic to set the EnterpriseCourseEnrollmentSource for the Enterprise Enrollments through offers and management task.

[2.0.27] - 2019-11-26
---------------------

* Make the SAML enterprise active at login and de-activate other enterprises learner is linked to.

[2.0.26] - 2019-11-26
---------------------

* Updated xapi exports with an active enterprise setting for users with multiple linked enterprises.

[2.0.25] - 2019-11-22
---------------------

* Added logic to set the EnterpriseCourseEnrollmentSource for the Enterprise Enrollments background task.

[2.0.24] - 2019-11-21
---------------------

* Added logic to set the EnterpriseCourseEnrollmentSource for Enterprise Enrollments by URL.

[2.0.23] - 2019-11-20
---------------------

* Display enterprise course enrollments separate from non-enterprise course enrollments in the "Enterprise Customer Learner" Django admin form

[2.0.22] - 2019-11-18
---------------------

* Custom get function in EnterpriseCustomerUserManager to enable multiple user enterprises.

[2.0.21] - 2019-11-14
---------------------

* Remove success url validation for select enterprise page.

[2.0.20] - 2019-11-13
---------------------

* Added Source to Enterprise API Enrollments.

[2.0.19] - 2019-13-08
---------------------

* Add manual enrollment audit creation for enrollments created in Manage Learners form.

[2.0.19] - 2019-11-13
---------------------

* Sorted results of enterprise-learner API by active flag in descending order so active enterprises are on the top

[2.0.18] - 2019-11-13

---------------------

* Better handling when Integrated Channels return unexpected results


[2.0.17] - 2019-11-08
---------------------

* Added in models to track enterprise enrollment source and updated the Enterprise Course Enrollments and PendingEnrollments to track that source.

[2.0.16] - 2019-11-07
---------------------

* Address defect ENT-2463. Add protection within EnterpriseCustomerUser model in enroll method during coure enrollments.

[2.0.15] - 2019-11-07
---------------------

* Added missing migration for EnterpriseCustomerUser

[2.0.14] - 2019-11-07
---------------------

* Add Enterprise selection page to allow a learner to select one of linked enterprises

[2.0.13] - 2019-11-07
---------------------

* Add manual order creation to enterprise manual enrollment admin form

[2.0.12] - 2019-11-06
---------------------

* Update 'EnterpriseCustomerUser' model. Add 'create_order_for_enrollment'. Called during 'enroll'. Will create an ecommerce order for pending course enrollments.

[2.0.11] - 2019-11-06
---------------------

* Add management command to populate sample enterprise data in the LMS within devstack

[2.0.10] - 2019-10-29
---------------------

* Add method to Ecommerce API client to call the manual enrollment order API

[2.0.9] - 2019-10-28
---------------------

* Updated image url field in content metadata export for cornerstone and degreed

[2.0.8] - 2019-10-22
---------------------

* Adding logging to search/all/ endpoint in discovery api client

[2.0.7] - 2019-10-21
---------------------

* Added certificate and grades api calls for transmitting learner export to integrated channels

[2.0.6] - 2019-10-18
---------------------

* Add query_param to remove expired course runs from /enterprise/api/v1/enterprise_catalogs/UUID/ endpoint

[2.0.5] - 2019-10-15
---------------------

* Adding migration file to remove EnterpriseCustomerEntitlement from table schema

[2.0.4] - 2019-10-10
--------------------

* Added preview button for EnterpriseCustomerCatalogs in EnterpriseCustomer admin page


[2.0.3] - 2019-10-09
---------------------

* Add message box to code management page and admin portal

[2.0.2] - 2019-10-07
--------------------

* Updating create_enterprise_course_enrollment task to accept object ids instead of python objects to play nicely with async.
* Also converts course_id to str before handing it to task to play nicely with async.

[2.0.1] - 2019-10-07
--------------------

* Commenting out code while troubleshooting signal issue in the LMS

[2.0.0] - 2019-10-02
---------------------

* Removing EnterpriseCustomerEntitlement code

[1.11.0] - 2019-10-02
---------------------

* Adding post-save receiver to spin off EnterpriseCourseEnrollment creation tasks on CourseEnrollment creation signals

[1.10.8] - 2019-10-01
---------------------

* Resolved issue with content_metadata image_url.

[1.10.7] - 2019-09-25
---------------------

* Added support to transmit single learner data.

[1.10.6] - 2019-09-25
---------------------

* Added ability set supported languages in Cornerstone Global Config.

[1.10.5] - 2019-09-23
---------------------

* Updating enterprise_learner_portal LMS API calls to refer to new function locations in the LMS.


[1.10.4] - 2019-09-05
---------------------

* Added new endpoint basic_list to EnterpriseEnrollment.

[1.10.3] - 2019-09-19
---------------------
* Add enable_portal_reoprting_config_screen field to EnterpriseCustomer model.
* Add enable_portal_reporting_config_screen to EnterpriseCustomerSerializer.


[1.10.2] - 2019-09-18
---------------------
* Added ability to set password on reporting configuration.

[1.10.1] - 2019-09-16
---------------------

* Upgrading requirements.

[1.10.0] - 2019-09-16
---------------------

* Add learner portal configuration fields to EnterpriseCustomer model.

[1.9.12] - 2019-09-06
---------------------

* Implement "move to completed" functionality for Enterprise Enrollments.

[1.9.11] - 2019-09-05
---------------------

* Add new field 'marked_done' to EnterpriseCourseEnrollment.

[1.9.10] - 2019-09-04
---------------------

* Improved enterprise enrollment workflow logging.

[1.9.9] - 2019-08-29
--------------------

* Updated learner portal enrollments endpoint to require an enterprise id.

[1.9.8] - 2019-08-29
--------------------

* Corrected missing db migration data for the EnterpriseCustomerReportingConfigurations model

[1.9.7] - 2019-08-28
--------------------

* Added API endpoints for EnterpriseCustomerReportingConfigurations and updated permissions to use Feature role based auth.

[1.9.6] - 2019-08-23
--------------------

* Added XAPILearnerDataTransmissionAudit model for xapi integrated channel.

[1.9.5] - 2019-08-21
--------------------

* Preventing another error in enterprise_learner_portal serializer when certificate info is None.

[1.9.4] - 2019-08-20
--------------------

* Adding type check to enterprise_learner_portal serializer.
* Adding enterprise_learner_portal to quality check commands.

[1.9.3] - 2019-08-20
--------------------

* Fix for include course run dates and pacing type in the course description sent to SAP. Prior release (1.9.2) did not include bumping the version in __init__.py.

[1.9.2] - 2019-08-20
--------------------

* Include course run dates and pacing type in the course description sent to SAP.

[1.9.1] - 2019-08-19
--------------------

* Added enterprise_learner_portal to MANIFEST.in file to recursively grab files app on build
* Minor fixes to typos and an image link

[1.9.0] - 2019-08-12
--------------------

* Adding enterprise_learner_portal app to support data needs of frontend enterprise learner portal app

[1.8.9] - 2019-08-15
--------------------

* Remove tincan from src directory

[1.8.8] - 2019-08-01
--------------------

* For CornerstoneCourseListAPI handled corner cases for default values.

[1.8.7] - 2019-07-31
--------------------

* Added history models for PendingEnrollment and PendingEnterpriseCustomerUser.
* Sending default values for required fields in Cornerstone Course List API

[1.8.6] - 2019-07-25
--------------------

* Add/Update logs for GrantDataSharingPermissions and DataSharingConsentView views to improve monitoring.

[1.8.5] - 2019-07-25
--------------------

* Change coupon code request email from address.

[1.8.4] - 2019-07-24
--------------------

* Introduce enterprise catalog queries.

[1.8.3] - 2019-07-24
--------------------

* Upgrade python requirements.

[1.8.2] - 2019-07-23
--------------------

* Log success of coupon code request email send.

[1.8.1] - 2019-07-22
--------------------

* Show linked enterprise customer on `Enterprise Customer Learners` and `System wide Enterprise User Role Assignments` admin screen

[1.8.0] - 2019-07-22
--------------------

* Replace edx-rbac jwt utils with edx-drf-extensions jwt utils

[1.7.3] - 2019-07-19
--------------------

* Change the way we declare dependencies so we can avoid breaking make upgrade in edx-platform.

[1.7.2] - 2019-07-18
--------------------

* Added ability to send user's progress to cornerstone


[1.7.1] - 2019-07-15
--------------------

* Reverted page size of SAPSF inactive user results from 1000 to 500

[1.7.0] - 2019-07-15
--------------------

* Pin certain constraints from edx-platform so that edx-enterprise will install properly there.

[1.6.23] - 2019-07-15
---------------------

* Upgrade python requirements

[1.6.22] - 2019-07-11
---------------------

* Revert changes made in 1.6.20

[1.6.21] - 2019-07-11
---------------------

* Added additional logging for enterprise api

[1.6.20] - 2019-07-10
---------------------

* Updated catalog preview URL on enterprise customer catalog admin list display

[1.6.19] - 2019-07-09
---------------------

* Added ability to skip keys if their value is None for content exporter

[1.6.18] - 2019-06-24
---------------------

* Changed page size of SAPSF inactive user results from 500 to 1000

[1.6.17] - 2019-06-20
---------------------

* Fixed Server Error on enterprise course enroll url caused by week_to_complete None value

[1.6.16] - 2019-06-20
---------------------

* Capture user attributes sent by cornerstone

[1.6.15] - 2019-06-18
---------------------

* Fix error where the search/all/ endpoint in discovery is called with course_key=None

[1.6.14] - 2019-06-18
---------------------

* Pass language code instead of language name in languages field of course-list API for cornerstone

[1.6.13] - 2019-06-17
---------------------

* Improved logging of `unlink_inactive_sap_learners` command and matching social auth user by `uid` field

[1.6.12] - 2019-06-14
---------------------

* Updated discovery clients to always call the enterprise customer site if available

[1.6.11] - 2019-06-14
---------------------

* Update the format of course_duration in xAPI payload data.

[1.6.10] - 2019-06-13
---------------------

* Remove old catalog model field.

[1.6.9] - 2019-06-12
--------------------

* Install django-filter so this app is compatible with newer DRF packages.

[1.6.8] - 2019-06-11
--------------------

* Fix error in enrollment flow caused by the way course keys were parsed.

[1.6.7] - 2019-06-11
--------------------

* added enable_audit_data_reporting in EnterpriseCustomerSerializer

[1.6.6] - 2019-06-10
--------------------

* Use OAuth2AuthenticationAllowInactiveUser as oauth2 authentication instead of BearerAuthentication for course-list API.

[1.6.5] - 2019-06-06
--------------------

* Use edx-rbac functions and pin edx-rbac so that we can continue to release edx-enterprise.

[1.6.4] - 2019-06-05
--------------------

* Upgrade packages to get latest edx-drf-extensions version.

[1.6.3] - 2019-06-04
--------------------

* Remove RBAC waffle switch

[1.6.2] - 2019-05-31
--------------------

* Remove old style catalogs

[1.6.1] - 2019-05-30
--------------------

* Fallback to request.auth if JWT cookies are not found.

[1.6.0] - 2019-05-29
--------------------

* Added new integrated channel `cornerstone` with course-list API.

[1.5.9] - 2019-05-27
--------------------

* Reverting changes from 1.5.6.

[1.5.8] - 2019-05-24
--------------------

* Bumping version to 1.5.8. 1.5.7 was tagged and released without actually bumping the version

[1.5.7] - 2019-05-24
--------------------

* Updating get_paginated_content ent catalog method to use count value given from discovery service

[1.5.6] - 2019-05-24
--------------------

* Fix the way a course identifier is found for a given course run.

[1.5.5] - 2019-05-21
--------------------

* Clean up rbac authorization related waffle switches and logic

[1.5.4] - 2019-05-20
--------------------

* Updating test packages to be inline with edx-platform. Specifically Bleach >2.1.3

[1.5.3] - 2019-05-16
--------------------

* Add total number of weeks to view from data consent screen

[1.5.2] - 2019-05-15
--------------------

* Remove usages of get_decoded_jwt_from_request from rbac in favor of get_decoded_jwt from edx-drf-extensions

[1.5.1] - 2019-05-09
--------------------

* Updating consent granted view to redirect to dashboard if consent is not required

[1.5.0] - 2019-05-08
--------------------

* Add sync_learner_profile_data flag to data returned by enterprise-learner endpoint

[1.4.10] - 2019-05-08
---------------------

* Add enterprise customer column in the list_display admin interface for `SystemWideEnterpriseUserRoleAssignment`
* Update `SystemWideEnterpriseUserRoleAssignment` admin interface search to support search by enterprise customer

[1.4.9] - 2019-05-02
--------------------

* Upgrade edx-rbac version

[1.4.8] - 2019-04-26
--------------------

* Reduce course mode match exception log level

[1.4.7] - 2019-04-17
--------------------

* Fix invalid object attribute references in exception message

[1.4.6] - 2019-04-17
--------------------

* Stop masking discovery call failures from the client for enterprise catalog endpoint calls.

[1.4.5] - 2019-04-12
--------------------

* Revise course mode match exception message in CourseEnrollmentView.

[1.4.4] - 2019-04-11
--------------------

* Revise course load exception message in CourseEnrollmentView.

[1.4.3] - 2019-04-11
--------------------

* Added `availability` key to default content filter for ECC.

[1.4.2] - 2019-04-11
--------------------

* Update `assign_enterprise_user_roles` management command to also assign catalog and enrollment api admin roles.

[1.4.1] - 2019-04-10
---------------------

* Update `RouterView` if user is already enrolled in course run of a course then user will land on that course_run.

[1.4.0] - 2019-04-08
--------------------

* Add new rbac permission checks to enterprise api endpoints.

[1.3.11] - 2019-04-07
---------------------

* Update context for `enterprise-openedx-operator` role.

[1.3.10] - 2019-04-03
---------------------

* Provide ability to add ECE even if course is closed from manage learners admin interface.

[1.3.9] - 2019-03-29
--------------------

* Update role metadata for `edx-openedx-operator` role.

----------

[1.3.8] - 2019-03-29
--------------------

* Update `assign_enterprise_user_roles` management command to also assign enterprise operator role.

[1.3.7] - 2019-03-28
--------------------

* Add data migration for adding edx enterprise operator role.

[1.3.6] - 2019-03-27
--------------------

* Introduce rbac models for feature specific roles within edx-enterprise.

[1.3.5] - 2019-03-22
--------------------

* Assign an enterprise learner role to new EnterpriseCustomerUser.

[1.3.4] - 2019-03-21
--------------------

* Management command to assign enterprise roles to users.

[1.3.3] - 2019-03-21
--------------------

* Fixed error in enrollment flow when audit track is selected and no DSC required.

[1.3.2] - 2019-03-18
--------------------

* Adding django admin for SystemWideEnterpriseUserRoleAssignments.

[1.3.1] - 2019-03-13
--------------------

* Optimizations around unlinking of SAP Success factor inactive users

[1.3.0] - 2019-03-07
--------------------

* Introducing Enterprise System Wide Roles and edx-rbac.

[1.2.12] - 2019-02-15
---------------------

* Updating enterprise views with new logging
* Updating enterprise views to render new error page in a number of circumstances

[1.2.11] - 2019-02-07
---------------------

* Allow admins with enterprise permissions to edit Data Sharing Consent Records


[1.2.10] - 2019-01-30
---------------------

* Include Enterprise Catalog UUID in Enterprise Customer django admin inline.

[1.2.9] - 2019-01-23
--------------------

* Upgrade requirements, and add code-annotations.
* Add PII annotations to all apps in this repo.
* Enable PII checking during CI.

[1.2.8] - 2019-01-22
--------------------

* Revert 1.2.4 to restore DSC functionality.

[1.2.7] - 2019-01-18
--------------------

* Replace error level log with info level log when enterprise user is not enrolled in course yet and the `transmit_learner_data` command is run

[1.2.5] - 2019-01-16
--------------------

* Updating launch_points data in SapSuccessFactorsContentMetadataExporter so SuccessFactors can be mobile ready

[1.2.4] - 2019-01-16
--------------------

* Remove HandleConsentEnrollment view and replaced with a function inside GrantDataSharingPermissions view. Removed
  GET side effect

[1.2.3] - 2019-01-10
---------------------

* Add management command "unlink_inactive_sap_learners" to unlink inactive SAP learners from the related enterprises

[1.2.2] - 2019-01-09
---------------------

* Update styling for future courses start date visibility

[1.2.1] - 2018-12-21
---------------------

* Handle /search/all/ endpoint large catalog queries to discovery through HTTP POST

[1.2.0] - 2018-12-19
---------------------

* Updating the course grade api url called in lms api

[1.1.4] - 2018-12-19
---------------------

* Upgrade django-simple-history required version

[1.1.3] - 2018-12-18
---------------------

*  Add option on EnterpriseCustomer for displaying code management in portal

[1.1.2] - 2018-12-12
---------------------

* Update EnterpriseCustomer model to introduce customer type field

[1.1.1] - 2018-12-11
---------------------

* Use LMS-defined segment track() method

[1.1.0] - 2018-12-06
---------------------

* Updating EnterpriseCustomerReportingConfiguration model. ManyToMany relationship with EnterpriseCustomerCatalog
* Updating EnterpriseCustomerReportingConfigurationAdminForm validation
* Updating EnterpriseCustomerReportingConfigurationSerializer

[1.0.6] - 2018-11-28
---------------------

* Added username and user email in EnterpriseCustomerUserAdmin list display.
* Added search by username and user email in EnterpriseCustomerUserAdmin.

[1.0.5] - 2018-11-14
---------------------

* Added enterprise api for requesting additional coupon codes.

[1.0.4] - 2018-11-07
---------------------

* Make HTTP POST request to get catalog results from discovery.

[1.0.3] - 2018-11-02
---------------------

* Fix translations for enterprise pages.

[1.0.2] - 2018-10-25
---------------------

* Updated EnterpriseCustomerReportingConfiguration model with PGP key

[1.0.1] - 2018-10-24
---------------------

* Made autocohorting API availability based on a configuration option.

[1.0.0] - 2018-10-16
--------------------
* Upgrade edx-drf-extensions with refactored imports.
* Remove Hawthorn testing for upcoming backward incompatible change.

[0.73.6] - 2018-10-04
---------------------
* SuccessFactors: Submit batch/chunk of OCN items to tenants until error status

[0.73.5] - 2018-09-21
---------------------
* Added ability to query enterprises by slug on the with_access_to endpoint

[0.73.4] - 2018-09-17
---------------------

* Added ability to assign cohort upon enrollment.
* Added ability to unenroll in enrollment API.

[0.73.3] - 2018-09-14
---------------------

* Added Country field to the EnterpriseCustomer model.

[0.73.2] - 2018-09-11
---------------------

* Fixed 500 error on enterprise customer admin screen.

[0.73.1] - 2018-08-30
---------------------

* Remove the SailThru flags for enterprise learner when un-linking it from enterprise.

[0.73.0] - 2018-08-21
---------------------

* Changed permission logic and added filtering options for the enterprise with_access_to endpoint.

[0.72.7] - 2018-08-20
---------------------

* Added preview field that takes user to Discovery with elastic search results for the catalog

[0.72.6] - 2018-08-17
---------------------

* Added management command to send course enrollment and course completion info for enterprise customers.

[0.72.5] - 2018-08-09
---------------------

* Revise management command query to include all potentially-applicable enrollment records

[0.72.4] - 2018-08-08
---------------------

* Move some fields from Global Degreed Configuration to Enterprise Degreed Configuration.

[0.72.3] - 2018-08-08
---------------------

* Added LearnerInfoSerializer and CourseInfoSerializer for serializing xAPI payload data.

[0.72.2] - 2018-07-27
---------------------

* Added endpoint to check a user's authorization to Enterprises based on membership in a given django group.

[0.72.1] - 2018-07-26
---------------------

* Added missing migrations for xAPI LRS Configuration model


[0.72.0] - 2018-07-24
---------------------

* Implemented reporting channel of course completion via X-API

[0.71.2] - 2018-07-23
---------------------

* Add thumbnail images in exported metadata content by content type.

[0.71.1] - 2018-07-23
---------------------

* Updated message for invalid Enterprise Customer Catalog references in B2B enrollment workflow.

[0.71.0] - 2018-07-20
---------------------

* Updated TinCanPython package to support python 3
* Updated UUID field to nowrap in admin interface of enterprise customer catalog model.

[0.70.8] - 2018-07-13
---------------------

* Display customer catalog content filter's default value on enterprise customer admin.

[0.70.7] - 2018-07-12
---------------------

* Make customer catalog content filter's default value configurable.

[0.70.6] - 2018-07-09
---------------------

* Pass catalog value only when provided on enterprise course enrollment page.

[0.70.5] - 2018-07-06
---------------------

* Send learner data transmissions to integrated channels by course key and course run id.

[0.70.4] - 2018-07-03
---------------------

* Use query param "catalog" instead of "enterprise_customer_catalog_uuid" for catalog based enterprise discounts.

[0.70.3] - 2018-06-29
---------------------

* Apply enterprise catalog conditional offer by the provided enterprise catalog UUID.

[0.70.2] - 2018-06-28
---------------------

* Modify enterprise branding config API to use enterprise slug as the lookup_field.

[0.70.1] - 2018-06-27
---------------------

* Paginate linked learners list on manage learners Django admin view.

[0.70.0] - 2018-06-26
---------------------

* Add unique slug field to EnterpriseCustomer.

[0.69.6] - 2018-06-25
---------------------

* Update requirements to fix pip install issues and to keep in line with edx-platform.

[0.69.5] - 2018-06-25
---------------------

* Fix the Direct-to-Audit enrollment issue in case of course instead of course run.

[0.69.4] - 2018-06-20
---------------------

* Strip locale values.

[0.69.3] - 2018-06-20
---------------------

* Add and transmit customer specific locales so that SuccessFactors show course title and description.

[0.69.2] - 2018-06-18
---------------------

* Fix the Direct-to-Audit enrollment issue in case of course.

[0.69.1] - 2018-06-07
---------------------

* 500 error when attempting to enroll using course-level URL.

[0.69.0] - 2018-05-31
---------------------

* Add a `progress_v2` option in the reporting config to be used for data API fetching.

[0.68.9] - 2018-05-31
---------------------

* Increased character limit from 20 to 255 for field title in EnterpriseCustomerCatalog model
* Reorder list display for EnterpriseCustomerCatalogAdmin
* Add sorting order for EnterpriseCustomerCatalogAdmin

[0.68.8] - 2018-05-30
---------------------

* Mark ECU as inactive internally if SAPSF says the ECU is inactive on their side.

[0.68.7] - 2018-05-24
---------------------

* Admin tooling enterprise customer reporting configuration enhancement - Order by Enterprise Customer Name.

[0.68.6] - 2018-05-22
---------------------

* Update DSC to show notification interstitial communicating to enterprise learner they are leaving company's site.

[0.68.5] - 2018-05-17
---------------------

* Configuration to show/hide original price on enterprise course landing page.

[0.68.4] - 2018-05-16
---------------------

* Remove constraints on the reporting config.

[0.68.3] - 2018-05-11
---------------------

* Update enrollment api authorization to check group permissions.

[0.68.2] - 2018-05-10
---------------------

* Dropped sap_success_factors_historicalsapsuccessfactorsenterprisecus80ad table.

[0.68.1] - 2018-05-09
---------------------

* Add `json` report type.

[0.68.0] - 2018-05-09
---------------------

* Allow reporting configs to work for arbitrary data and report types.

[0.67.8] - 2018-05-04
---------------------

* Added ordering to resolve warnings of probable invalid pagination data.

[0.67.7] - 2018-04-23
---------------------

* Update the messages when an enterprise learner leave an organization.

[0.67.6] - 2018-04-20
---------------------

* Update user session when they become an Enterprise learner.

[0.67.5] - 2018-04-18
---------------------

* Added ability to specify data sharing consent wording on a per enterprise basis.

[0.67.4] - 2018-04-12
---------------------

* Add configuration to allow replacing potentially sensitive SSO usernames.

[0.67.3] - 2018-04-05
---------------------

* Improved integrated channel logging.

[0.67.2] - 2018-04-05
---------------------

* Fix the enterprise manage learner django admin tool is loading correctly for chrome users.

[0.67.1] - 2018-04-04
---------------------

* Integrated channel refactoring cleanup.

[0.67.0] - 2018-03-26
---------------------

* Refactored integrated channel code to allow for greater flexibility when transmitting content metadata.

[0.66.2] - 2018-03-26
---------------------

* Update isort version and sort imports after making consent and integrated_channels first party apps.

[0.66.1] - 2018-03-23
---------------------

* Temporarily disable linked learners list on manage learners Django admin view until paging can be added.

[0.66.0] - 2018-03-05
---------------------

* Add EnterpriseCustomerCatalog course detail endpoint.

[0.65.8] - 2018-02-23
---------------------

* Add "Enrollment Closed" in course title if the course is no longer open for enrollment.

[0.65.7] - 2018-02-14
---------------------

* Support multiple emails in EnterpriseCustomerReportingConfiguration.
* Only require email(s) in EnterpriseCustomerReportingConfiguration if the selected delivery method is email.

[0.65.6] - 2018-02-13
---------------------

* Remove the renderer.py file.

[0.65.5] - 2018-02-13
---------------------

* Add functionality in enterprise django admin for transmitting courses metadata related to a specific enterprise.

[0.65.4] - 2018-02-09
---------------------

* Indicate when a course is no longer open for enrollment by updating course title for transmit courses metadata.

[0.65.3] - 2018-02-06
---------------------

* Decreased SuccessFactors course metadata chunk size from 1000 to 500, per SAP's recommendation.

[0.65.2] - 2018-02-05
---------------------

* Updated the "Data Sharing Policy" language.

[0.65.1] - 2018-02-02
---------------------

* Provide an option for enterprise to pull enterprise catalog API in XML format not just JSON.

[0.65.0] - 2018-01-30
---------------------

* Add migration for removing old password fields from the database.

[0.64.0] - 2018-01-29
---------------------

* Removed code references to old password fields.

[0.63.0] - 2018-01-25
---------------------

* Improved handling of password fields on database models.

[0.62.0] - 2018-01-18
---------------------

* Exclude credit course mode option from course enrollment page.

[0.61.6] - 2018-01-18
---------------------

* Group Name, Active, Site, and Logo together.
* Rename "Provider id" form label to "Identity Provider"
* Rename "Entitlement id" form label to "Seat Entitlement"
* Rename "Coupon URL" form label to "Seat Entitlement URL"
* Add a "View details" hyperlink next to identity provider drop-down.
* Add a "Create a new catalog" link under the Catalog drop-down.
* Add a "View details" hyperlink next to catalog field, if catalog is selected.
* Add a "Create a new identity provider" link under the Identity Provider drop-down.

[0.61.5] - 2018-01-18
---------------------

* Include start date in all course runs title when pushing to Integrated Channels.

[0.61.4] - 2018-01-12
---------------------

* Add localized currency to enterprise landing page.

[0.61.3] - 2018-01-11
---------------------

* Fix enterprise logo stretching issue in enterprise sidebar on course/program enrollment pages.

[0.61.2] - 2018-01-09
---------------------

* Add missing migrations for sap_success_factors and degreed.

[0.61.1] - 2018-01-09
---------------------

* Update django admin list view for enterprise customer model.

[0.61.0] - 2018-01-09
---------------------

* SuccessFactors Admin Update: Enterprise Customer Configuration.

[0.60.0] - 2018-01-03
---------------------

* Add sftp configuration options for EnterpriseCustomerReportingConfiguration.

[0.59.0] - 2017-12-28
---------------------

* Add check for active companies when getting list of channels

[0.58.0] - 2017-12-22
---------------------

* Add save_enterprise_customer_users command.

[0.57.0] - 2017-12-21
---------------------

* Remove references to SSO IdP config drop_existing_session flag.

[0.56.5] - 2017-12-20
---------------------

* Fix templates to use new bootstrap bundle library.

[0.56.4] - 2017-12-19
---------------------

* Fix syntax error in template-embedded Javascript.

[0.56.3] - 2017-12-14
---------------------

* Make sure root url has a fallback for proxy enrollment email links.

[0.56.2] - 2017-12-13
---------------------

* Add course_enrollments API endpoint to swagger specification.

[0.56.1] - 2017-12-13
---------------------

* Add publish_audit_enrollment_url flag to EnterpriseCustomerCatalog.

[0.56.0] - 2017-12-13
---------------------

* Update create_enterprise_course_enrollment command.

[0.55.7] - 2017-12-13
---------------------

* Ensure that proxy enrollment email links trigger SSO.

[0.55.6] - 2017-12-12
---------------------

* Check site configuration for from email address first

[0.55.5] - 2017-12-11
---------------------

* Added course start date to title string for instructor-led courses

[0.55.4] - 2017-12-06
---------------------

* Redirect to embargo restriction message page if user is blocked from accessing course.

[0.55.3] - 2017-12-05
---------------------

* Add integrated channel configuration info to course metadata push task logging.

[0.55.2] - 2017-12-04
---------------------

* Include additional context for learner data transmission job exceptions.

[0.55.1] - 2017-11-30
---------------------

* Track enterprise course enrollment events.

[0.55.0] - 2017-11-29
---------------------

* Add Degreed as new integrated channel.

[0.54.1] - 2017-11-29
---------------------

* Increase font size on data sharing consent page.

[0.54.0] - 2017-11-28
---------------------

* Introduce the bulk enrollment/upgrade api endpoint for Enterprise Customers.

[0.53.19] - 2017-11-28
----------------------

* Do not change EnterpriseCustomerReportingConfiguration.password on update.

[0.53.18] - 2017-11-28
----------------------

* Add Identity Provider's ID to enterprise customer API response.

[0.53.17] - 2017-11-27
----------------------

* Remove inaccurate landing page audit track language.

[0.53.16] - 2017-11-22
----------------------

* Use LMS_INTERNAL_ROOT_URL instead of LMS_ROOT_URL for API base.

[0.53.15] - 2017-11-16
----------------------

* Use the cryptography package instead of the unmaintained pycrypto.

[0.53.14] - 2017-11-14
----------------------

* Link learner to enterprise customer directly using "tpa_hint" URL parameter.

[0.53.13] - 2017-11-14
----------------------

* Update DSC policy to match legal requirements.

[0.53.12] - 2017-11-09
----------------------

* Remove "Discount provided by..." text on the program landing page.

[0.53.11] - 2017-11-06
----------------------

* Removing SAP_USE_ENTERPRISE_ENROLLMENT_PAGE switch via django waffle and use landing page URL instead of track selection page.

[0.53.10] - 2017-11-02
----------------------

* Move data sharing policy to its own partial to improve theming of the data sharing consent page

[0.53.9] - 2017-11-02
---------------------

* Apply appropriate content filtering to the EnterpriseCustomerCatalog detail endpoints.

[0.53.8] - 2017-11-02
---------------------

* Show generic info message on enterprise course enrollment page.

[0.53.7] - 2017-10-30
---------------------

* Added inline admin form to EnterpriseCustomer admin for EnterpriseCustomerCatalog.

[0.53.6] - 2017-10-30
---------------------

* Fix error for empty course start date on DSC page.

[0.53.5] - 2017-10-26
---------------------

* Fetch catalog courses in large chunks to avoid API limit.

[0.53.4] - 2017-10-26
---------------------

* Preserve catalog querystring on declining DSC.

[0.53.3] - 2017-10-26
---------------------

* Fixing logo size on themed enterprise pages

[0.53.2] - 2017-10-24
---------------------

* Remove unused dependency on django-extensions

[0.53.1] - 2017-10-24
---------------------

* Fix alteration in querystring parameters for decorator "enterprise_login_required".

[0.53.0] - 2017-10-24
---------------------

* Get rid of the `EnterpriseIntegratedChannel` model and any other related but unused code.

[0.52.10] - 2017-10-23
----------------------

* Fix migration issue for `enabled-course-modes` field of EnterpriseCustomerCatalog

[0.52.9] - 2017-10-20
---------------------

* Update the call level to enrollment uls from EnterpriseCustomer to EnterpriseCustomerCatalog.

[0.52.8] - 2017-10-20
---------------------

* Update EnterpriseApiClient.get_enterprise_courses to account for EnterpriseCustomerCatalogs.

[0.52.7] - 2017-10-20
---------------------

* Update course enrollment view for enterprise enabled course modes.

[0.52.6] - 2017-10-19
---------------------

* Update the EnterpriseCustomerCatalog migration.


[0.52.5] - 2017-10-19
---------------------

* Add EnterpriseCustomerCatalog UUID as query parameter "catalog" in enterprise course and program enrollment URL's.

[0.52.4] - 2017-10-18
---------------------

* Upgrade django-simple-history to 1.9.0. Add needed migrations.

[0.52.3] - 2017-10-18
---------------------

* Introducing EnterpriseCustomerReportingConfig model for enterprise_reporting.

[0.52.2] - 2017-10-18
---------------------

* If a course is unenrollable, the program and course enrollment landing pages will display only a subset of information.

[0.52.1] - 2017-10-15
---------------------

* Change a log level from `error` to `info` in our LMS API Client, as it wasn't really an error.

[0.52.0] - 2017-10-14
---------------------

* Implement a direct-audit-enrollment pathway for course enrollment.
* Implement a RouterView that the enrollment URLs have to go through before redirection to a downstream view.

[0.51.5] - 2017-10-11
---------------------

* Added enabled_course_modes JSONField to EnterpriseCustomerCatalog model

[0.51.4] - 2017-10-11
---------------------

* Added UTM parameters to marketing, track selection, and course/program enrollment URLs returned by Enterprise API.

[0.51.3] - 2017-10-10
---------------------

* Fix bug related to EnterpriseCustomer creation form introduced with 0.51.0.

[0.51.2] - 2017-10-10
---------------------

* Modify EnterpriseCustomer.catalog_contains_course to check EnterpriseCustomerCatalogs.

[0.51.1] - 2017-10-06
---------------------

* Refactor user-facing DSC view's logic.

[0.51.0] - 2017-10-05
---------------------

* Make discovery-service lookups site-aware

[0.50.1] - 2017-10-03
---------------------

* Improved robustness for `force_fresh_session` decorator in conjunction with `enterprise_login_required`
* Consciously avoid attempting to sync back details for SAPSF users who aren't linked via SSO

[0.50.0] - 2017-10-03
---------------------

* Add contains_content_items endpoint to EnterpriseCustomerViewSet and EnterpriseCustomerCatalogViewSet.

[0.49.0] - 2017-10-02
---------------------

* Rewrite all of our CSS in SASS/SCSS.
* Use Bootstrap for our modals.
* Fix existing course modal UI issues using Bootstrap & SASS/SCSS.

[0.48.2] - 2017-09-29
---------------------

* Step 2 in making enrollment email template linked to enterprise. Remove site from model. No migration.

[0.48.1] - 2017-09-25
---------------------

* Step 1 in making enrollment email template linked to enterprise. Make 'site' nullable, add 'enterprise_customer'.


[0.48.0] - 2017-09-25
---------------------

* Add extra details to the program enrollment landing page.

[0.47.1] - 2017-09-25
---------------------

* Add proper permissions/filtering schemes for all of our endpoints.

[0.47.0] - 2017-09-21
---------------------

* Step 3 in safe deployment of removing old consent models: make migrations to delete the outstanding fields/models.

[0.46.8] - 2017-09-21
---------------------

* Step 2 in safe deployment of removing old consent models: remove `require_account_level_consent`, but no migration.

[0.46.7] - 2017-09-21
---------------------

* Step 1 in safe deployment of removing old consent models: make `require_account_level_consent` nullable.

[0.46.6] - 2017-09-21
---------------------

* Added some log messages to trace possible 404 issue.

[0.46.5] - 2017-09-21
---------------------

* Remove old account-level consent features as well as consent from EnterpriseCourseEnrollment.

[0.46.4] - 2017-09-20
---------------------

* Abstract away usage of `configuration_helpers`.

[0.46.3] - 2017-09-19
---------------------

* Make bulk enrollment emails more intelligent

[0.46.2] - 2017-09-19
---------------------

* Add exception handling for transmit course metadata task.

[0.46.1] - 2017-09-18
---------------------

* Remove the `auth-user` endpoint completely.

[0.46.0] - 2017-09-15
---------------------

* Allow multi-course enrollment for enterprise users in admin.

[0.45.0] - 2017-09-14
---------------------

* Modified enterprise-learner API endpoint to include the new DataSharingConsent model data.

[0.44.0] - 2017-09-08
---------------------

* Added MVP version of the Programs Enrollment Landing Page.

[0.43.5] - 2017-09-08
---------------------

* Wrapped API error handling into the clients themselves.

[0.43.4] - 2017-09-07
---------------------

* Removed the text if there is no discount on the course enrollment landing page.

[0.43.3] - 2017-09-06
---------------------

* Ensure that segment is loaded and firing page events for all user facing enterprise views.

[0.43.2] - 2017-09-06
---------------------

* Display the enterprise discounted text on the course enrollment landing page.

[0.43.1] - 2017-09-05
---------------------

* Remove support for writing consent_granted in enterprise-course-enrollment api.

[0.43.0] - 2017-08-31
---------------------

* Add architecture for program-scoped data sharing consent.

[0.42.0] - 2017-08-24
---------------------

* Do not create baskets and orders for audit enrollments.

[0.41.0] - 2017-08-24
---------------------

* Migrate the codebase to the new `consent.models.DataSharingConsent` model for when dealing with consent.

[0.40.7] - 2017-08-23
---------------------

* Fix bug causing 500 error on course enrollment page when the course does not have a course image configured.

[0.40.6] - 2017-08-23
---------------------

* Update Consent API to use Discovery worker user for auth, rather than request user.

[0.40.5] - 2017-08-23
---------------------

* Update SAP course export to use enterprise courses API.

[0.40.4] - 2017-08-23
---------------------

* Fix 500 server error on enterprise course enrollment page.

[0.40.3] - 2017-08-21
---------------------

* Change landing page course modal to use discovery api for populating course details.

[0.40.2] - 2017-08-16
---------------------

* Increase capability and compatibility of Consent API.

[0.40.1] - 2017-08-11
---------------------

* Add new unified DataSharingConsent model to the `consent` app.

[0.40.0] - 2017-08-08
---------------------

* Add Enterprise API Gateway for new Enterprise Catalogs and Programs endpoints.
* Add /enterprise/api/v1/enterprise-catalogs/ endpoint.
* Add /enterprise/api/v1/enterprise-catalogs/{uuid}/ endpoint.
* Add /enterprise/api/v1/programs/{uuid}/ endpoint.

[0.39.9] - 2017-08-08
---------------------

* Added management command "create_enterprise_course_enrollments" for missing enterprise course enrollments.

[0.39.8] - 2017-08-04
---------------------

* Fixed session reset decorator bug.

[0.39.7] - 2017-08-04
---------------------

* Make whether Enterprise Customers get data for audit track enrollments configurable.

[0.39.6] - 2017-08-02
---------------------

* Fixed the text cutoff in the bottom of the course info overlay.

[0.39.5] - 2017-08-02
---------------------

* Only send one completion status per enrollment for SAP SuccessFactors.

[0.39.4] - 2017-08-01
---------------------

* Create Audit enrollment in E-Commerce system when user enrolls in the audit mode in enterprise landing page.

[0.39.3] - 2017-07-28
---------------------

* Remove Macro use from swagger api config as it is not supported by AWS.


[0.39.2] - 2017-07-27
---------------------

* Introduce new endpoint to the Enterprise API to query for courses by enterprise id.

[0.39.1] - 2017-07-27
---------------------

* Ensure catalog courses API endpoint users are associated with an EnterpriseCustomer.

[0.39.0] - 2017-07-24
---------------------

* Officially include Consent application by ensuring it is installable.

[0.38.7] - 2017-07-22
---------------------

* Add a new Consent application.
* Add initial implementation of a generic Consent API.

[0.38.6] - 2017-07-21
---------------------

* Remove SSO-related consent capabilities

[0.38.5] - 2017-07-19
---------------------

* Add page_size in querystring and data mapping template to fix "next" and "previous" urls in API response.

[0.38.4] - 2017-07-18
---------------------

* Fix DSC Policy Language Needs

[0.38.3] - 2017-07-14
---------------------

* Fix dependency installation process in setup.py.

[0.38.2] - 2017-07-14
---------------------

* Add consent declined message to course enrollment landing page.

[0.38.1] - 2017-07-13
---------------------

* Remove requirement on too-new django-simple-history version
* Require slightly older django-config-models version

[0.38.0] - 2017-07-11
---------------------

* Move to edx-platform release-focused testing
* Add Django 1.11 support in Hawthorn testing branch

[0.37.1] - 2017-07-11
---------------------

* Update Enterprise landing page styling/language

[0.37.0] - 2017-07-06
---------------------

* Update enterprise catalog api endpoint so that api returns paginated catalogs.

[0.36.11] - 2017-06-29
----------------------

* Update DSC page language.

[0.36.10] - 2017-06-29
----------------------

* Introducing SAP_USE_ENTERPRISE_ENROLLMENT_PAGE switch via django waffle.

[0.36.9] - 2017-06-28
---------------------

* Refactor of automatic session termination logic.

[0.36.8] - 2017-06-28
---------------------

* Enforce data sharing consent at login for SSO users only if data sharing consent is requested at login.

[0.36.7] - 2017-06-25
---------------------

* UI tweaks to the enterprise landing page and course overview modal.

[0.36.6] - 2017-06-25
---------------------

* Disable atomic transactions for CourseEnrollmentView to ensure that new EnterpriseCustomerUser records are saved to
  the database in time for ecommerce API calls.


[0.36.5] - 2017-06-23
---------------------

* Apply automatic session termination logic to enterprise landing page based on enterprise customer configuration.

[0.36.4] - 2017-06-21
---------------------

* Sort course modes in landing page.


[0.36.3] - 2017-06-21
---------------------

* Fix for being unable to create course catalog clients due to upstream removal of the library.

[0.36.2] - 2017-06-21
---------------------

* Add the ability to pass limit, offset and page_size parameters to enterprise catalog courses.


[0.36.1] - 2017-06-20
---------------------

* Properly bump PyPI to latest changes from v0.36.0.


[0.36.0] - 2017-06-20
---------------------

* Migrate from old, monolithic python-social-auth to latest, split version.
* Rework the NotConnectedToOpenEdX exception to be just one, and to say which method/dependency is missing.


[0.35.2] - 2017-06-20
---------------------

* Fix Next and Previous page urls for enterprise catalog courses.


[0.35.1] - 2017-06-15
---------------------

* Displayed course run price with entitlement on landing page and course information overlay


[0.35.0] - 2017-06-15
---------------------

* Allow account-level data sharing consent in a course-specific context


[0.34.7] - 2017-06-14
---------------------

* Enable "Continue" button flows on enterprise landing page


[0.34.6] - 2017-06-14
---------------------

* Fixed layout of data sharing consent decline modal on mobile view


[0.34.5] - 2017-06-09
---------------------

* Add Django 1.10 support back


[0.34.4] - 2017-06-09
---------------------

* Added course information overlay


[0.34.3] - 2017-06-07
---------------------

* Make enterprise landing page url available in the enterprise api and SAP course export.


[0.34.2] - 2017-06-06
---------------------

* Fix UI issues (unexpected html escape) on enterprise landing page.


[0.34.1] - 2017-06-06
---------------------

* Bug fix for Data sharing consent pop up page.


[0.34.0] - 2017-06-05
---------------------

* Update data backing and behavior of enterprise landing page
* Fix template prioritization bug
* Fix URL rendering in enterprise login decorator


[0.33.24] - 2017-06-02
----------------------

* UI updates for data sharing consent page.


[0.33.23] - 2017-06-02
----------------------

* Fix a bug with unexpected image data in SAP course export job.


[0.33.22] - 2017-06-02
----------------------

* Add an `EnterpriseApiClient` method for getting enrollment data about a single user+course pair
* Add logic to enterprise landing page that redirects users to the course when already registered


[0.33.21] - 2017-06-01
----------------------

* UI updates for course mode selection in enterprise landing page.


[0.33.20] - 2017-05-23
----------------------

* Migrate from mako templates to django templates


[0.33.19] - 2017-05-18
----------------------

* Display account created/linked messages on enterprise landing page


[0.33.18] - 2017-05-17
----------------------

* Add Enable audit enrollment flag


[0.33.17] - 2017-05-16
----------------------

* Add django admin for enterprise course enrollment models


[0.33.16] - 2017-05-15
----------------------

* Bug fixes for SAP learner completion data passback.

[0.33.15] - 2017-05-10
----------------------

* Additional minor UI updates for enterprise landing page.


[0.33.14] - 2017-05-10
----------------------

* Add new externally managed consent option for enterprise customers.

[0.33.13] - 2017-05-09
----------------------

* Fix invalid API Gateway URIs


[0.33.12] - 2017-05-03
----------------------

* Add enterprise landing page


[0.33.11] - 2017-05-02
----------------------

* Add tpa hint if available for launchURLs for SAP Course metadata push.

[0.33.10] - 2017-05-02
----------------------

* Fix bug with inactivating SAP courses that are no longer in the catalog.


[0.33.9] - 2017-04-26
---------------------

* Fix enterprise logo validation message for max image size limit


[0.33.8] - 2017-04-26
---------------------

* Updated calls to get_edx_api_data as its signature has changed in openedx.


[0.33.7] - 2017-04-24
---------------------

* Redirect to login instead of raising Http404 if EnterpriseCustomer missing.
* Add confirmation_alert_prompt_warning to context of account-level consent view.


[0.33.6] - 2017-04-21
---------------------

* Increase max size limit for enterprise logo


[0.33.5] - 2017-04-20
---------------------

* Added vertical hanging indent mode to isort settings and adjusted current imports


[0.33.4] - 2017-04-18
---------------------

* Enforce login for course-specific data sharing consent views.


[0.33.3] - 2017-04-18
---------------------

* Fixed the CSS for the expand arrow in the data sharing consent page.


[0.33.2] - 2017-04-17
---------------------

* Update Data Sharing Consent message.


[0.33.1] - 2017-04-17
---------------------

* Order enterprise customers by name on enterprise customer django admin


[0.33.0] - 2017-04-11
---------------------

* Improve accounting for inactive courses for SAP course export.


[0.32.1] - 2017-04-06
---------------------

* Bug Fix: Added Handling for user enrollment to courses that do not have a start date.


[0.32.0] - 2017-04-06
---------------------

* Refine SAP course export parameters


[0.31.4] - 2017-04-05
---------------------

* Added missing migration file for recent string updates


[0.31.3] - 2017-04-04
---------------------

* Modified SAP completion status data to correctly indicate a failing grade to SAP systems.

[0.31.2] - 2017-04-03
---------------------

* Bugfix: Resolve IntegrityError getting raised while linking existing enterprise users when data sharing consent is
  disabled for the related enterprise.

[0.31.1] - 2017-03-31
---------------------

* Bugfix: Allow unlinking of enterprise learners with plus sign or certain other characters in email address.

[0.31.0] - 2017-03-30
---------------------

* Edited UI and error strings.

[0.30.0] - 2017-03-27
---------------------

* Fully implements sap_success_factors transmitters and client to communicate with the SAP SuccessFactors API,
  and to handle auditing and other business logic for both catalog and learner data calls.


[0.29.1] - 2017-03-27
---------------------

* Support for segment.io events on data sharing consent flow


[0.29.0] - 2017-03-23
---------------------

* Updates integrated_channels management command `transmit_learner_data` to support sending completion data for
  self-paced courses, and to use the Certificates API for instructor-paced courses.

[0.28.0] - 2017-03-23
---------------------

* New data sharing consent view supporting failure_url parameter


[0.27.6] - 2017-03-21
---------------------

* Removed OAuth2Authentication class from API viewset definitions


[0.27.5] - 2017-03-17
---------------------

* Updated api.yaml to resolve swagger configuration issues.


[0.27.4] - 2017-03-17
---------------------

* Allows enterprise enrollments to be made on servers that sit behind a load balancer.


[0.27.3] - 2017-03-16
---------------------
* Added integrated_channels management command to transmit courseware metadata to SAP SuccessFactors.

[0.27.2] - 2017-03-10
---------------------

* Added integrated_channels management command to transmit learner completion data to SAP SuccessFactors.

[0.27.1] - 2017-03-13
---------------------

* Added api.yaml and api-compact.yaml files to introduce api endpoints for catalog api-manager.


[0.27.0] - 2017-03-02
---------------------

* Added API endpoint for fetching catalogs and catalog courses.

[0.26.3] - 2017-03-02
---------------------

* Added integrated_channels to MANIFEST.in to properly include migrations for the new packages.

[0.26.2] - 2017-03-02
---------------------

* Fixed package listing in setup.py to avoid import errors when using as a library

[0.26.1] - 2017-02-28
---------------------

* Added support for retrieving access token from SAP SuccessFactors
* Added indicator in Sap SuccessFactors admin tool for checking the configuration's access to SuccessFactors.

[0.26.0] - 2017-02-28
---------------------

* Formally introducing new integrated_channels apps
* Adding new models and admin interfaces for integrated_channel and sap_success_factors

[0.25.0] - 2017-02-28
---------------------

* Refactor _enroll_users() method to pay down technical debt
* Improve admin messaging around enrollment actions

[0.24.0] - 2017-02-27
---------------------

* API for SSO pipeline is simplified to a single element.
* SSO users are linked to relevant Enterprise Customer when data sharing consent is disabled.

[0.23.2] - 2017-02-22
---------------------

* SSO users are not created as EnterpriseCustomerUsers until all consent requirements have been fulfilled.


[0.22.1] - 2017-02-20
---------------------

* Course Catalog API degrades gracefully in absence of Course Catalog service.


[0.22.0] - 2017-02-14
---------------------

* Added API endpoint for fetching entitlements available to an enterprise learner


[0.21.2] - 2017-02-07
---------------------

* Add id in EnterpriseCustomerUserSerializer fields


[0.21.0] - 2017-01-30
---------------------

* Add UI handling for course-specific data sharing consent


[0.20.0] - 2017-01-30
---------------------

* Add ability to select existing learners to be enrolled in courses from admin


[0.19.1] - 2017-01-30
---------------------

* Resolved conflicting urls for User API endpoint.


[0.19.0] - 2017-01-30
---------------------

* Added read-only enterprise API endpoint for IDAs.
* Moved utility functions from api.py to utils.py


[0.18.0] - 2017-01-27
---------------------

* Add the ability to notify manually-enrolled learners via email.


[0.17.0] - 2017-01-25
---------------------

* Add the EnterpriseCourseEnrollment model and related methods


[0.16.0] - 2017-01-25
---------------------

* Fix a bug preventing a course catalog from being unlinked from an EnterpriseCustomer


[0.15.0] - 2017-01-25
---------------------

* Enroll users in a program.


[0.14.0] - 2017-01-20
---------------------

* Added view of seat entitlements on enterprise admin screen


[0.13.0] - 2017-01-06
---------------------

* Dynamically fetch available course modes in the Manage learners admin


[0.12.0] - 2017-01-05
---------------------

* Create pending enrollment for users who don't yet have an account.


[0.11.0] - 2017-01-05
---------------------

* Added links from the Manage Learners admin panel to individual learners.


[0.10.0] - 2017-01-04
---------------------

* Added the ability to search the Manage Learners admin panel by username and email address.


[0.9.0] - 2016-12-29
--------------------

* In django admin page for enterprise customer added alphabetical ordering for
  catalog drop down and displayed catalog details link next to selected catalog.


[0.8.0] - 2016-12-08
--------------------

* added the branding information api methods to return the enterprise customer logo on the basis of provider_id or uuid.
* Updated the logo image validator to take an image of size maximum of 4kb.


[0.7.0] - 2016-12-07
--------------------

* Added a feature to enroll users in a course while linking them to an
  enterprise customer.


[0.6.0] - 2016-12-04
--------------------

* Fixed EnterpriseCustomer form to make Catalog field optional
* Added user bulk linking option
* Added Data Sharing Consent feature


[0.5.0] - 2016-11-28
--------------------

* Added checks to make sure enterprise customer and identity provider has one-to-one relation.
* Added a helper method to retrieve enterprise customer branding information


[0.4.1] - 2016-11-24
--------------------

* Fixed User.post_save handler causing initial migrations to fail


[0.4.0] - 2016-11-21
--------------------

* Set up logic to call course catalog API to retrieve catalog listing to attach to EnterpriseCustomer.


[0.3.1] - 2016-11-21
--------------------

* Fixed missing migration.


[0.3.0] - 2016-11-16
--------------------

Added
^^^^^

* Added Pending Enterprise Customer User model - keeps track of user email linked to Enterprise Customer, but not
  yet used by any user.
* Added custom "Manage Learners" admin view.

Technical features
^^^^^^^^^^^^^^^^^^

* Added sphinx-napoleon plugin to support rendering Google Style docstrings into documentation properly (i.e.
  make it recognize function arguments, returns etc.)
* Added translation files


[0.2.0] - 2016-11-15
--------------------

* Linked EnterpriseCustomer model to Identity Provider model


[0.1.2] - 2016-11-04
--------------------

* Linked EnterpriseCustomer model to django Site model


[0.1.1] - 2016-11-03
--------------------

* Enterprise Customer Branding Model and Django admin integration


[0.1.0] - 2016-10-13
--------------------

* First release on PyPI.
* Models and Django admin integration
