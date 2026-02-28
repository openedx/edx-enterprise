# [edx-enterprise] Add CourseModeCheckoutStarted pipeline step

Blocked by: [openedx-platform] Replace enterprise customer checkout import with filter call

Add a `CheckoutEnterpriseContextInjector` pipeline step for `CourseModeCheckoutStarted` in `enterprise/filters/course_modes.py`. The step calls `enterprise_customer_for_request(request)` (deferred import from `openedx.features.enterprise_support.api` until epic 17) and injects the enterprise customer dict into the context under the key `'enterprise_customer'`. The pipeline step is wired into `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` by the openedx-platform ticket.

## A/C

- `CheckoutEnterpriseContextInjector(PipelineStep)` is defined in `enterprise/filters/course_modes.py` and injects `enterprise_customer` into the context.
- Unit tests cover the pipeline step.
