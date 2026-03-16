# Epic: Logistration Enterprise Context

JIRA: ENT-11568

## Purpose

Three logistration views (`login_form.py`, `registration_form.py`, `login.py`) in openedx-platform import multiple functions from `enterprise_support` to customize the login/registration page and post-login redirect behavior for enterprise SSO learners.

## Approach

Use three migration paths: (1) a new `LogistrationContextRequested` openedx-filter that edx-enterprise uses to enrich and modify the login/registration page context with enterprise data; (2) the existing `StudentRegistrationRequested` filter (already in openedx-filters) for registration form field gating; and (3) a new `PostLoginRedirectURLRequested` openedx-filter to allow edx-enterprise to inject an enterprise selection page redirect after successful login.

## Blocking Epics

None.
