0013 Creating Custom Groups for Enterprise Customers
##############################

Status
******

**Pending**

Terminology
*******
*Enterprise Group* - Collection of enterprise customer users connected to a policy/subsidy

*Membership* - Relationship between enterprise learner and enterprise group


Context
*******

Groups is a new feature that will allow admins the flexibility to control and distribute funding. These changes will improve the user management and budgeting from the admin perspective, as well as adding personalization to the learner experience. Groups will be associated with a learner credit budget. In the past, we’ve used workarounds to sidestep this functionality, but with this new implementation, we will increase scalability and personalization.

EnterpriseGroup
*********************
**Model properties**
------
- uuid, name, created, modified, history
- enterprise_customer_uuid (FK to EnterpriseCustomer, related_name=”groups”)
- policy_uuid

**/api/v1/enterprise-group/<group_uuid>**
The root URL for reading metadata about a group.

**CRUD**
------
**api/v1/enterprise-group/?group_uuid=[group-uuid]&learner_uuid=[enterprise_customer_user_id]&enterprise_uuid=[enterprise_uuid]**

Inputs
==========
- ``group_uuid`` (query param, optional): Get the basic information about the group
- ``learner_uuid`` (query param, optional): Get all the groups that the learner is associated with 
- ``enterprise_uuid`` (query param, optional): Get all the groups under the enterprise


**GET (list) enterprise learners**
------
**api/v1/enterprise-group/<group_uuid>/learners/(?learner_ids)**

Inputs
==========
- ``learner_ids`` (query param, optional): Specifies a list of enterprise_customer_user_ids 

Outputs
==========
Returns a paginated list of learners that are associated with the enterprise group uuid 



**POST assign learners**
------
**api/v1/enterprise-group/<group_uuid>/assign_learners**

Inputs
==========
- ``learner_uuids`` (POST data, required): A list of enterprise_customer_user_ids to assign to the group


**POST remind learners**
------
**api/v1/enterprise-group/<group_uuid>/remind_learners**

Inputs
==========
- ``learner_uuids`` (POST data, required): A list of enterprise_customer_user_ids to assign to the group


**POST remove learners**
------
**api/v1/enterprise-group/<group_uuid>/remove_learners**

Inputs
==========
- ``learner_uuids`` (POST data, required): A list of enterprise_customer_user_ids to assign to the group

   
EnterpriseGroupMembership
*********************
**Model properties**
------
- uuid, created, modified, history
- group (FK to EnterpriseGroup with related name ``members``)
- enterprise_customer_user_id (FK to EnterpriseCustomerUser with related_name of ``memberships``)
- status [``PENDING, ACCEPTED, EXPIRED, REMOVED``]
- last_reminded (timestamp)

TODO: Status will be set to expired if created is older than 90 days and status is still pending for PII reasons. Still need to think about how it is going to be updated (management command, filtered results, TBD).

Further Improvements
*********************
- Groups will have analytics, learning goals, and other customizations associated with them in the future
