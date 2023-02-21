Enterprise subsidy enrollments and entitlements
===============================================

Status
------

Accepted

Context
-------

Enterprise course enrollment and course entitlement records can come into existence from different types of subsidies:

- Subscription licenses - we’d want to track the license uuid at time of enrollment creation.

- Learner credit subsidy transactions - we’d want to track the transaction uuid at time of enrollment or entitlement creation.

- Coupon codes - not yet tracked in the context of this ADR.

On top of architecting the tables to support subsidy licenses and credit transactions we want to build a system that can support other, not yet known types of subsidies as there is the chance that new ones will be added in the future.

We will create a new EnterpriseCourseEntitlement model, which will mirror the purpose of the EnterpriseCourseEnrollment model but instead track a subsidy that is not yet connected to a course enrollment and will support converting to said enrollment.

Decisions
---------

**Why have `EnterpriseCourseEntitlement`s?**

There are situations where enterprise admins give a learner a subsidy for a specific course, but that course does not yet have a valid run for the learner to enroll in. Entitlements allow us to track the subsidy for the specific user before the enrollment can be created so that when the time comes for the learner to start/create the enrollment, the entitlment can be easily converted and used. These entitlements can also be gathered, tracked and provided as a metric for the admins of any enterprise customer.

It is also important that these models link to and mirror the state of the B2C enrollment and entitlement models (both CourseEntitlement and CourseEnrollment), such that there is a 1:1 relationship between B2C and B2B rows for enterprise related enrollments and entitlements. Meaning that when we write an enterprise enrollment or entitlement, we should also create the B2C counterpart for that record.

**Why implement abstract table inheritance and what is `EnterpriseFulfillmentSource`?**

- We can more easily track the entitlement to enrollment lifecycle.

- The null/not-null data integrity constraints are easy to grok and helps keep our data valid.

- Inheritance means that things are easily extendable. As we onboard new types of fulfillments, we can simply add new child models.

**Benefits of this rework**

- It helps standardize subsidy consumption for multiple content types and providers, given that the content is represented in the edX catalog service.

- We can do this in a de-coupled way with Event-bus and/or polling.

- We can easily support new subsidy types

A rework of the enterprise subsidy enrollment models and creation of enterprise entitlements
--------------------------------------------------------------------------------------------

The new enterprise entitlement table:

**EnterpriseCourseEntitlement**

\-------------------------------\

- uuid, created, modified, history (boilerplate)
- enterprise_customer_user_id (NOT NULL, FK to EnterpriseCustomerUser)
- enterprise_course_enrollment_id (NULL, FK to EnterpriseCourseEnrollment)
- converted_at (NULL DateTime).
- (cached property) course_entitlement_id (query look up of related CourseEntitlement)

-- TBD: A built in method of entitlement conversion to enrollment


Reworked and added table inheritance to all subsidy based enrollment tables. As such all subsidy based fulfillment records will have access to the following fields:

**EnterpriseFulfillmentSource**

\------------------------------\

- uuid, created, modified, history (boilerplate)
- fulfillment_type (NOT NULL, char selection: (`license`, `learner_credit`, `coupon_code`))
- enterprise_course_entitlement (NOT NULL, FK to EnterpriseCourseEntitlement)
- enterprise_course_enrollment (NOT NULL, FK to EnterpriseCourseEnrollment)
- is_revoked (Default False, Bool)


Models inheriting `EnterpriseFulfillmentSource`:


**LicensedEnterpriseCourseEnrollment** (inherited from EnterpriseFulfillmentSource)

\-----------------------------------------\

- license_uuid (NOT NULL, UUID field)


**LearnerCreditEnterpriseCourseEnrollment** (inherited from EnterpriseFulfillmentSource)

\---------------------------------------------\

- transaction_id (NOT NULL, UUID field)


[NOTE] Even though these models are labeled as `...Enrollment`s, they can reference entitlements as well as enrollments. In fact, despite both `enterprise_course_entitlement` `enterprise_course_enrollment` both being nullable, there is validation on the `EnterpriseFulfillmentSource` which will guarantees one of these values must exist.

To support interactions with these reworked and new models, we've buffed out the bulk enrollment (`enroll_learners_in_courses`) EnterpriseCustomerViewSet view to support subsidy enrollments. `enrollment_info` parameters supplied to the endpoint can now include transaction ID's that will detected and realized into a `LearnerCreditEnterpriseCourseEnrollment` record.

**How we'd use this in code**

.. code-block::

  # In the parent class...
  @classmethod
  def get_fulfillment_source(cls, enrollment_id, entitlement_id=None):
    return cls.objects.select_related(
      # all child tables joined here
    ).filter(
      cls.enterprise_course_enrollment=enrollment_id
    )
    # do kwargs stuff here to optionally pass in a non-null
    # entitlement id to filter by...

  @property
  def fulfillment_status(self):
    if not self.enterprise_course_enrollment:
      return 'entitled'
    return 'enrolled'


Consequences
------------

- Table inheritance means that we’ll most likely have to do JOINs in our code and in our analytics/reporting.

- There exists a subsidy based enrollment table already (`LicensedEnterpriseCourseEnrollment`), any form of concrete inheritance added to this existing table would result in needing a data migration. Using abstract model inheritance avoids this complexity.

Further Improvements
--------------------

- Verify transaction ID's are real on creation through the bulk enrollment endpoint. Note that this is not wholly necessary as we expect requests to come from an authenticated __system__ user.
- Add a programatic way to turn entitlements into enrollments
- Continue extending the `enroll_learners_in_courses` endpoint to support bulk entitlement creation of entitlements. (suggestion here is that if course run keys are supplied for enrollments, if course uuid's are supplied then we generate entitlements instead)

Alternatives Considered
-----------------------

- `Concrete model inheritance`: Concretely inherit the children of the subsidy fulfillment table meaning that shared fields would be contained in the parent table. However, due to complexity required to do data and schema migrations was too great to justify the costs and risks. Abstract inheritance still gives us the benefits of:

  1. flexibility to have subsidy-specific methods and fields on the child models.
  2. common behavior of methods via the base class.
  3. common and unique uuid field for easy reference across systems (e.g. the uuid is what's stored on ledger transactions to commit them).

  and as for reporting and analytics, we can easily write a view to aggregate these two tables into a single relation especially with a fulfillment type column.

- `One big table`: Jam everything into one big table; almost every field is optional - might do code-level validation in the model’s save() method to ensure the presence of non-null fields depending on type of fulfillment.

- `Table-hierarchy based on FK relationships`: Instead of strict inheritance, we could implement subsidy based tables that rely on foreign keys instead. This option was dropped as it required all the same work as concrete table inheritance with a subset of the benefits.
