Segment events
==============

``Edx-enterprise`` emits several Segment events.

edx.bi.user.enterprise.onboarding
---------------------------------

Emitted when a new ``EnterpriseCourseEnrollment`` record gets created.

The event contains these properties:

- **pathway**: A string identifying the mechanism through which the ``EnterpriseCourseEnrollment`` was created. See below
  for possible values.
- **course_run_id**: EdX course ID associated with the enrollment.
- **url_path**: The url path the user was visiting when the enterprise course enrollment got created. Can be null when
  the enrollment is created outside of a learner's request (for example admin or REST API enrollments).

The possible values of the **pathway** property are:

- **admin-enrollment**: Enrollment was created by an admin via the "Manage Learners" tool.
- **pending-admin-enrollment**: Enrollment was created from a pending enrollment record previously set up by an admin
  via the "Manage Learners" tool.
- **rest-api-enrollment**: Enrollment was created via the REST API.
- **data-consent-page-enrollment**: Enrollment was created when learner submitted the form on the data sharing consent
  page.
- **course-landing-page-enrollment**: Enrollment was created when learner enrolled via the course landing page.
- **direct-audit-enrollment**: Enrollment was created via the direct audit enrollment mechanism.
- **customer-admin-enrollment**: Enrollment was created by a customer admin via the frontend app admin portal.

edx.bi.user.enterprise.enrollment.course
----------------------------------------

Emitted when the enterprise app enrolls a user into a course.

The event contains these properties:

- **label**: EdX course ID associated with the enrollment.
- **enterprise_customer_uuid**: UUID of the ``EnterpriseCustomer`` associated with the enrollment.
- **enterprise_customer_name**: Name of the ``EnterpriseCustomer`` associated with the enrollment.
- **mode**: The mode of the enrollment (audit, verified, etc.).

edx.bi.user.consent_form.shown
------------------------------

Emitted when the learner is presented with the data sharing consent page.

The event contains these properties:

- **deferCreation**: True when creation of course enrollment is deferred.
- **successUrl**: URL to redirect the user to if consent is provided.
- **failureUrl**: URL to redirect the user to in case consent is not provided.
- **courseId**: EdX course ID of the associated course.
- **programId**: ID of the associated program.

edx.bi.user.consent_form.accepted
---------------------------------

Emitted after the learner grants data sharing consent.

The event contains the same properties as the `edx.bi.user.consent_form.shown`_ event.

edx.bi.user.consent_form.denied
-------------------------------

Emitted after the learner denies data sharing consent.

The event contains the same properties as the `edx.bi.user.consent_form.shown`_ event.
