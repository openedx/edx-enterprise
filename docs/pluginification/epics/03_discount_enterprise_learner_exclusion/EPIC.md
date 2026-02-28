# Epic: Discount Enterprise Learner Exclusion

JIRA: ENT-11564

## Purpose

`openedx-platform/openedx/features/discounts/applicability.py` uses lazy imports of `is_enterprise_learner` from `enterprise_support.utils` in two functions (`can_receive_discount` and `can_show_streak_discount_coupon`) to exclude enterprise learners from LMS-controlled discounts, creating hidden import-time coupling to edx-enterprise.

## Approach

Introduce a new `DiscountEligibilityCheckRequested` openedx-filter with signature `run_filter(user, course_key, is_eligible)` that allows pipeline steps to set `is_eligible` to `False`. Replace both lazy `is_enterprise_learner` imports and calls in `applicability.py` with a single call to this filter. Implement a new `DiscountEligibilityStep` pipeline step in edx-enterprise that returns `{"is_eligible": False}` when `is_enterprise_learner(user)` is True.

## Blocking Epics

None. This epic has no dependencies and can start immediately.
