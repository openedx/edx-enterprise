# [openedx-filters] Add DiscountEligibilityCheckRequested filter

No tickets block this one.

Add a new `DiscountEligibilityCheckRequested` filter class to `openedx_filters/learning/filters.py`. This filter is invoked during discount applicability checks and allows pipeline steps to mark a user/course combination as ineligible for a discount. The filter accepts the Django User, the course key, and the current boolean eligibility flag, and returns the (possibly overridden) `is_eligible` bool along with the unchanged `user` and `course_key`. No exception class is required since this filter is configured with `fail_silently=True` and the caller falls back to the pre-filter value.

## A/C

- A new `DiscountEligibilityCheckRequested` class is added to `openedx_filters/learning/filters.py`, inheriting from `OpenEdxPublicFilter`.
- The filter type is `"org.openedx.learning.discount.eligibility.check.requested.v1"`.
- `run_filter(cls, user, course_key, is_eligible)` returns a tuple `(user, course_key, is_eligible)` where `is_eligible` is a bool.
- No exception subclass is defined on this filter.
- A unit test confirms that when `run_pipeline` returns `is_eligible=False`, the filter returns `False` for `is_eligible`.
