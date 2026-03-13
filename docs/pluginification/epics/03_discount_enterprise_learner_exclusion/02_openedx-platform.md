# [openedx-platform] Use DiscountEligibilityCheckRequested filter in discount applicability

Blocked by: [openedx-filters] Add DiscountEligibilityCheckRequested filter

Replace both lazy `from openedx.features.enterprise_support.utils import is_enterprise_learner` imports in `openedx/features/discounts/applicability.py` — one in `can_receive_discount` and one in `can_show_streak_discount_coupon` — with calls to the new `DiscountEligibilityCheckRequested` filter. The filter is called with the current `is_eligible` state (`True` at that point in the function) and the function short-circuits to return `False` when the filter returns `is_eligible=False`. Add the filter to `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py`. Update tests in `discounts/tests/test_applicability.py` to mock the filter rather than directly using enterprise model factories.

## A/C

- Both lazy `from openedx.features.enterprise_support.utils import is_enterprise_learner` imports are removed from `applicability.py`.
- In `can_receive_discount`, the `is_enterprise_learner(user)` check is replaced by `DiscountEligibilityCheckRequested.run_filter(user=user, course_key=course.id, is_eligible=True)`, returning `False` if `is_eligible` comes back `False`.
- In `can_show_streak_discount_coupon`, the same replacement is applied.
- `OPEN_EDX_FILTERS_CONFIG` in `lms/envs/common.py` contains an entry for `"org.openedx.learning.discount.eligibility.check.requested.v1"` with `fail_silently=True` and `pipeline=[]`.
- Tests in `discounts/tests/test_applicability.py` are updated to patch `DiscountEligibilityCheckRequested.run_filter` rather than importing enterprise models.
- No import of `enterprise_support` or `enterprise` remains in `applicability.py`.
