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

Groups is a new feature that will allow admins the flexibility to control and distribute funding. At a high level, a group is a subset of learners within an organization that is tied to an an enterprise customer's policy. A customer can have multiple policies and groups, and a learner can be in multiple groups. These changes will improve the user management and budgeting from the admin perspective, as well as adding personalization to the learner experience. Groups will be associated with a learner credit budget. In the past, we’ve used workarounds to sidestep this functionality, but with this new implementation, we will increase scalability and personalization.

EnterpriseGroup
*********************
**Model properties**
------
- uuid, name, created, modified, history (boilerplate)
- enterprise_customer_uuid (NOT NULL, FK to EnterpriseCustomer, related_name=”groups”)
- policy_uuid (NOT NULL, UUIDField)

**CRUD**
------
**api/v1/enterprise-group/<group_uuid>**

Outputs
==========
The root URL for getting the basic information about the group
::
   {
        'group_uuid': 'group_uuid',
        'name': 'group_name',
        'enterprise_customer_uuid': 'enterprise_customer_uuid',
        'policy_uuid': 'policy_uuid'
   }


**api/v1/enterprise-group/?learner_uuid=[enterprise_customer_user_id]&enterprise_uuid=[enterprise_uuid]**

Accepted Query Params
==========
- ``learner_uuid`` (optional): Get all the groups that the learner is associated with 
- ``enterprise_uuid`` (optional): Get all the groups under the enterprise

Outputs
==========
Returns a paginated list of groups filtered by the query params
::
   {
       'count': 1,
       'next': null,
       'previous': null,
       'results': [
           {
               'group_uuid': 'group_uuid',
               'name': 'group_name',
               'enterprise_customer_uuid': 'enterprise_customer_uuid',
               'policy_uuid': 'policy_uuid'
           }
       ]
   }


**GET (list) /learners**
------
**api/v1/enterprise-group/<group_uuid>/learners/**

Outputs
==========
Returns a paginated list of learners that are associated with the enterprise group uuid 
::
   {
       'count': 1,
       'next': null,
       'previous': null,
       'results': [
           {
               'learner_uuid': 'enterprise_customer_user_id',
               'enterprise_group_membership_uuid': 'enterprise_group_membership_uuid',
           }
       ]
   }


**POST /assign_learners**
------
**api/v1/enterprise-group/<group_uuid>/assign_learners**

Inputs
==========
- ``learner_uuids`` (POST data, required): A list of enterprise_customer_user_ids to assign to the group

Outputs
==========
Returns a list of the EnterpriseGroupMembership objects that were created 
::
   {
       'count': 1,
       'next': null,
       'previous': null,
       'results': [
           {
               'learner_uuid': 'enterprise_customer_user_id',
               'enterprise_group_membership_uuid': 'enterprise_group_membership_uuid',
           }
       ]
   }


**POST /remind_learners**
------
**api/v1/enterprise-group/<group_uuid>/remind_learners**

Inputs
==========
- ``learner_uuids`` (POST data, required): A list of enterprise_customer_user_ids to remind of their group membership


**POST /remove_learners**
------
**api/v1/enterprise-group/<group_uuid>/remove_learners**

Inputs
==========
- ``learner_uuids`` (POST data, required): A list of enterprise_customer_user_ids to assign to the group

   
EnterpriseGroupMembership
*********************
**Model properties**
------
- uuid, created, modified, history (boilerplate)
- group (NOT NULL, FK to EnterpriseGroup with related name ``members``)
- enterprise_customer_user_id (NOT_NULL, FK to EnterpriseCustomerUser with related_name of ``memberships``)
- status (NOT NULL, char selection: (`PENDING`, `ACCEPTED`, `EXPIRED`, `REMOVED`))
- last_reminded (default=NULL, TimeField)

TODO: Status will be set to expired if created is older than 90 days and status is still pending for PII reasons. Still need to think about how it is going to be updated (management command, filtered results, TBD).

Consequences
*********************
Now with the implementation of groups, this will be another facet that we will filter on. Now, not all learners under organizations necessarily have equal access to content. These subsets will provide a more personalized experience for the learner, and more control for the admin.

Further Improvements
*********************
Groups will have analytics, learning goals, and other customizations associated with them in the future
