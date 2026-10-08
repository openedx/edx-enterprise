Platform Support
----------------

Helpers that integrate edx-enterprise with the openedx-platform LMS: enterprise
customer lookups for the current request, data sharing consent checks, learner
portal, logistration and analytics event context, enterprise-specific account
settings, and the enrollment attribute override admin view.

This package was moved here from openedx-platform's
``openedx/features/enterprise_support/``. Its openedx-platform imports are
optional, so it imports cleanly without the platform installed, but the code
that relies on them only works inside the LMS.
