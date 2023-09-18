Enterprise subsidy enrollments and entitlements
===============================================

Status
------

Accepted (September 2023)

Context
-------

Enterprise typically uses environment configuration to control feature flags for soft/dark releases. For micro-frontends, this control involves environment variables that are set at build time and used to compile JavaScript source or configuration settings derived from the runtime MFE configuration API in edx-platform. For backend APIs, this control typically either involves configuration settings or, on occassion, a Waffle flag.

By solely relying on environment configuration, we are unable to dynamically control feature flags in production based on the user's context. 

For example, we may want to enable a feature for all staff users but keep it disabled for customers/users while it's in development. Similarly, we may want to enable a feature for a subset of specific users (e.g., members of a engineering squad) in production to QA before enabling it for all users. 

However, neither of these are really possible with environment configuration.


Decisions
---------

We will adopt the Waffle-based approach to feature flags for Enterprise micro-frontends in favor of environment variables or the MFE runtime configuration API. This approach will allow us to have more dynamic and granual control over feature flags in production based on the user's context (e.g., all staff users have a feature enabled, a subset of users have a feature enabled, etc.).


Consequences
------------

* We are introducing a third mechanism by which we control feature flags in the Enterprise micro-frontends. We may want to consider migrating other feature flags to this Waffle-based approach in the future. Similarly, such an exercise may be a good opportunity to revisit what feature flags exist today and what can be removed now that the associate features are stable in production.
* The majority of the feature flag setup for Enterprise systems lives in configuration settings. By moving more towards Waffle, the feature flag setup will live in databases and modified via Django Admin instead of via code changes.


Further Improvements
--------------------

* To further expand on the capabilities of Waffle-based feature flags, we may want to invest in the ability to enable such feature flags at the **enterprise customer** layer, where we may be able to enable soft-launch features for all users linked to an enterprise customer without needing to introduce new boolean fields on the ``EnterpriseCustomer`` model.

Alternatives Considered
-----------------------

* Continue using the environment variable to enabling feature flags like Enterprise has been doing the past few years. In order to test a disabled feature in production, this approach requires developers to allow the environment variable to be intentionally overridden by a `?feature=` query parameter in the URL. Without the query parameter in the URL, there is no alternative ways to temporarily enable the feature without impacting actual users and customers. Waffle-based feature flags give much more flexibility to developers to test features in production without impacting actual users and customers.
* Exposes a net-new API endpoint specific to returning feature flags for Enterprise needs. This approach was not adopted as it would require new API integrations within both the enterprise administrator and learner portal micro-frontends, requiring users to wait for additional network requests to resolve. Instead, we are preferring to include Waffle-based feature flags on existing API endpoints made by both micro-frontends.
