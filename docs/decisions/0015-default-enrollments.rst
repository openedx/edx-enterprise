==============================
Default Enterprise Enrollments
==============================

Status
======
Proposed - October 2024

Context
=======
Enterprise needs a solution for managing automated enrollments into "default" courses or specific course runs
for enterprise learners. Importantly, we need this solution to work for learners where we have no information
about the identity of learner who will eventually be associated with an ``EnterpriseCustomer``. For that reason,
the solution described below does not involve ``PendingEnrollments`` or anything similar -
that model/domain depends on knowing the email address of learners prior to their becoming associated with the customer.
The solution also needs to support customer-specific enrollment configurations
without tightly coupling these configurations to a specific subsidy type, i.e. we should be able in the future
to manage default enrollments via both learner credit and subscription subsidy types.

Core requirements
-----------------
1. Internal staff should be able to configure one or more default enrollments with either a course
   or a specific course run for automatic enrollment. In the case of specifying a course,
   the default enrollment flow should cause the "realization" of default enrollments for learners
   into the currently-advertised, enrollable run for a course.
2. Default Enrollments should be loosely coupled to subsidy type.
3. Unenrollment: If a learner chooses to unenroll from a default course, they should not be automatically re-enrolled.
4. Graceful handling of license revocation: Upon license revocation, we currently downgrade the learner’s
   enrollment mode to ``audit``. This fact should be visible from any new APIs exposed
   in the domain of default enrollments.
5. Non-enrollable courses: If a course becomes unenrollable, our intent is that default enrollments for such
   a course no longer are processed. Ideally this happens in a way that is observable to operators of the system.

Decision
========
We will implement two new models:
* ``DefaultEnterpriseEnrollmentIntention`` to represent the course/runs that
  learners should be automatically enrolled into, post-logistration, for a given enterprise.
* ``DefaultEnterpriseEnrollmentRealization``which represents the mapping between the intention
  and actual, **realized** enrollment record(s) for the learner/customer.

Qualities
---------
1. Flexibility: The ``DefaultEnterpriseEnrollmentIntention`` model will allow specification of either a course
   or course run.
2. Business logic: The API for this domain (future ADR) will implement the business logic around choosing
   the appropriate course run, for answering which if any catalogs are applicable to the course,
   and the enrollability of the course (the last of which takes into account the state of existing enrollment records).
3. Non-Tightly Coupled to subsidy type: Nothing in the domain of default enrollments will persist data
   related to a subsidy (although a license or transaction identifier will ultimately become associated with
   an ``EnterpriseCourseEnrollment`` record during realization).

Flexible content keys on the intention model
--------------------------------------------
The ``content_key`` on ``DefaultEnterpriseEnrollmentIntention`` is either a top-level course key
or a course run key during configuration to remain flexible for internal operators;
however, we will always discern the correct course run key to use for enrollment based on the provided ``content_key``.

Post-enrollment related models (e.g., ``EnterpriseCourseEnrollment`` and ``DefaultEnterpriseEnrollmentRealization``)
will always primarily be associated with the course run associated with the ``DefaultEnterpriseEnrollmentIntention``:
* If content_key is a top-level course, the course run key used when enrolling
  (converting to ``EnterpriseCourseEnrollment`` and ``DefaultEnterpriseEnrollmentRealization``)
  is the currently advertised course run.
* If the content_key is a specific course run, we'll always try to enroll in the explicitly
  configured course run key (not the advertised course run).

This content_key will be passed to the ``EnterpriseCatalogApiClient().get_content_metadata_content_identifier``
method. When passing a course run key to this endpoint, it'll actually return the top-level *course* metadata
associated with the course run, not just the specified course run's metadata
(this is primarily due to catalogs containing courses, not course runs, and we generally say that
if the top-level course is in a customer's catalog, all of its course runs are, too).

If the ``content_key`` configured for a ``DefaultEnterpriseEnrollmentIntention`` is a top-level course,
there is a chance the currently advertised course run used for future enrollment intentions might
change over time from previous redeemed/enrolled ``DefaultEnterpriseEnrollmentIntentions``.
However, this is mitigated in that the ``DefaultEnterpriseEnrollmentRealization``
ensures the resulting, converted enrollment is still related to the original ``DefaultEnterpriseEnrollmentIntention``,
despite a potential content_key vs. enrollment course run key mismatch.

Consequences
============
1. It's a flexible design.
2. It relies on a network call(s) to enterprise-catalog to fetch content metadata and understand which if any customer
   catalog are applicable to the indended course (we can use caching to make this efficient).
3. We're introducing more complexity in terms of how subsidized enterprise enrollments
   can come into existence.
4. The realization model makes the provenance of default enrollments explicit and easy to examine.
