Change Log
==========

..
   All enhancements and patches to edx-enteprise will be documented
   in this file.  It adheres to the structure of http://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (http://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
----------

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

* Removing SAP_USE_ENTERPRISE_ENROLLMENT_PAGE switch via django waffle and use landing page URL instead of track slection page.

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
* Conciously avoid attempting to sync back details for SAPSF users who aren't linked via SSO

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
