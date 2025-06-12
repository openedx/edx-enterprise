Percentage-based Waffle Flags by Enterprise Customer
==================================================

Status
------

Accepted (June 2025)

Context
-------

Enterprise currently uses Waffle flags to control feature rollouts across the platform. However, these flags are global and don't provide the ability to enable features for a specific percentage of users within a particular enterprise customer. This limitation makes it challenging to perform gradual rollouts or A/B testing for specific customers.

For example, we might want to enable a new feature for 50% of users in Enterprise A while keeping it disabled for all users in Enterprise B. The existing Waffle flag implementation doesn't support this level of granularity.

Decisions
---------

We will extend the Waffle flag system to support percentage-based rollouts at the enterprise customer level. This will be achieved by:

1. Creating a new model `EnterpriseWaffleFlagPercentage` that links a Waffle flag to an enterprise customer with a specific rollout percentage.
2. Extending the `EnterpriseWaffleFlag` class to check for enterprise-specific percentage overrides before falling back to the global flag settings.
3. The system will respect the following hierarchy when evaluating flag status:
   - Check if the user is linked to the specified enterprise
   - Look for an enterprise-specific percentage override
   - Fall back to the global flag settings if no override exists

Consequences
------------

* **Increased Flexibility**: Enables more granular feature rollouts by allowing different percentage rollouts per enterprise customer.
* **Improved Testing**: Facilitates A/B testing of features with specific customer segments.
* **Reduced Risk**: Allows for safer, more controlled rollouts by gradually increasing the percentage of users who see a feature.
* **Database Impact**: Introduces a new database table to store the enterprise-specific flag percentages.
* **Performance**: Adds a database query to check for enterprise-specific flag overrides when evaluating flag status.

Implementation Details
---------------------

The implementation includes:

1. A new `EnterpriseWaffleFlagPercentage` model that links a Waffle flag to an enterprise customer with a specific percentage.
2. Updates to the `EnterpriseWaffleFlag` class to check for enterprise-specific overrides.
3. Admin interface updates to manage enterprise-specific flag percentages.

Example usage:

```python
# Check if a feature is enabled for a specific enterprise customer
is_enabled = ENTERPRISE_FEATURE_FLAG.is_enabled(enterprise_customer_uuid=enterprise_uuid)
```

Alternatives Considered
----------------------

1. **Global Percentage Only**: Continue using the global Waffle flag percentage for all customers. This was rejected as it doesn't provide the needed per-customer control.

2. **Custom Feature Flag System**: Build a completely custom feature flag system. This was rejected as it would require significant development effort and maintenance overhead compared to extending the existing Waffle integration.

3. **Enterprise-specific Boolean Flags**: Create separate boolean flags for each enterprise. This was rejected as it would lead to flag proliferation and make it difficult to manage rollouts across multiple enterprises.

4. **Configuration Settings**: Use configuration settings to control feature visibility. This was rejected as it requires code deployments to change and doesn't support percentage-based rollouts.

Related Work
-----------

* ADR-0012: Waffle-based feature flags for Enterprise
* [Waffle Documentation](https://waffle.readthedocs.io/)
* [edx-toggles Documentation](https://github.com/openedx/edx-toggles)
