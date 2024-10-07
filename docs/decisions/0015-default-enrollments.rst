==============================
Default Enterprise Enrollments
==============================

Status
======
Proposed - October 2024

Context
=======
Enterprise needs a solution for managing automated enrollments into "default" courses or specific course runs
for enterprise learners. The solution needs to support customer-specific enrollment configurations
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
5. Non-enrollable courses: If a course becomes unenrollable, default enrollments should fail gracefully,
   and in a way that's obvious to the learner.

Decision
========
We will implement two new models, ``DefaultEnterpriseEnrollmentIntention`` to represent the course/runs that
learners should be default-enrolled into for a given enterprise, and ``DefaultEnterpriseEnrollmentRealization``
which represents the mapping between the intention and actual enrollment record(s) for the learner/customer.

Qualities
---------
1. Flexibility: The ``DefaultEnterpriseEnrollmentIntention`` model will allow specification of either a course
   or course run.
2. Business logic: The API for this domain (future ADR) will implement the business logic around choosing
   the appropriate course run, for answering which if any catalogs are applicable to the course,
   and the enrollability of the course.
3. Non-Tightly Coupled to subsidy type: Nothing in the domain of default enrollments will persist data
   related to a subsidy (although a license or transaction identifier will ultimately become associated with
   an ``EnterpriseCourseEnrollment`` record during realization).

Consequences
============
1. It's a flexible design.
2. It relies on a network call to enterprise-catalog to fetch content metadata (we can use caching to
   make this efficient).
3. We're introducing more complexity in terms of how subsidized enterprise enrollments
   can come into existence.
4. The realization model makes the provenance of default enrollments explicit and easy to examine.
