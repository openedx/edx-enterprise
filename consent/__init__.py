"""edX Enterprise's Consent application.

The consent application provides an API that enables the platform to prompt
the user to consent to share data about their activity and performance in
(a) particular course(s) with the enterprise customer that is (usually) subsidizing
their enrollment in those courses. When users grant consent to share data, that
agreement is recorded in the database in an easily auditable way.

The goals of the Consent API is that it can be used to provide consent at any type
of gate that an enterprise stands at.

"""

__version__ = "0.1.0"

default_app_config = "consent.apps.ConsentConfig"
