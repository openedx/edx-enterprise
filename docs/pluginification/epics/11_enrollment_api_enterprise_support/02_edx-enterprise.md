# [edx-enterprise] Add CourseEnrollmentStarted post-enrollment pipeline step

Blocked by: [openedx-platform] Remove enterprise enrollment API imports

Add a `EnterpriseEnrollmentPostProcessor` pipeline step for the existing `CourseEnrollmentStarted` filter in `enterprise/filters/enrollment.py`. The step checks whether the enrollment user is linked to an enterprise customer; if so, it calls `EnterpriseApiServiceClient` and `ConsentApiServiceClient` (deferred imports from `openedx.features.enterprise_support.api` until epic 17) to post the enterprise course enrollment and provide consent. The step will be registered in `OPEN_EDX_FILTERS_CONFIG` via `enterprise/settings/common.py` as part of epic 18.

## A/C

- `EnterpriseEnrollmentPostProcessor(PipelineStep)` is defined in `enterprise/filters/enrollment.py` and calls the enterprise and consent API clients.
- Unit tests cover the pipeline step for enterprise and non-enterprise users.
