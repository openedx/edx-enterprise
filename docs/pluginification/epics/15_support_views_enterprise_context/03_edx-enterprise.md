# [edx-enterprise] Add support view pipeline steps

Blocked by: [openedx-platform] Replace enterprise support view imports with filter calls

Add two pipeline steps in `enterprise/filters/support.py`:

1. `SupportContactEnterpriseTagInjector` for `SupportContactContextRequested` — appends `'enterprise_learner'` to the tags list when `enterprise_customer_for_request(request)` returns a non-empty result.

2. `SupportEnterpriseEnrollmentDataInjector` for `SupportEnrollmentDataRequested` — calls `get_enterprise_course_enrollments(user)` and `get_data_sharing_consents(user)` (deferred imports from `openedx.features.enterprise_support.api` until epic 17), builds the enrollment data dict keyed by course ID, and returns it.

## A/C

- `SupportContactEnterpriseTagInjector(PipelineStep)` appends `'enterprise_learner'` when the user is associated with an enterprise customer.
- `SupportEnterpriseEnrollmentDataInjector(PipelineStep)` returns the enterprise enrollment data dict keyed by course ID.
- Unit tests cover both pipeline steps.
