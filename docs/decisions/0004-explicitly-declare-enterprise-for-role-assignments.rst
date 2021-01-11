Enterprise role assignments will record a customer UUID
-------------------------------------------------------

Status
======

Accepted - January 2021

Context
=======

The ``SystemWideEnterpriseUserRoleAssignment`` model is used to grant role-based permissions
to enterprise users.  These permissions generally control the users' access to data
and ability to perform certain functions within an enterprise customer.  This assignment model does `not` currently
refer to any specific customer - the "context" to which a role is applied is inferred from
a user (an ``auth.User`` record) having been "linked" to a customer via the ``EnterpriseCustomerUser`` model.

However, a single ``auth.User`` may be linked to multiple ``EnterpriseCustomers``, and if that user
is assigned a role (such as ``enterprise_admin``), it is inferred that the role assignment applies
to **every** customer to which the user is linked.  This is undesirable; we generally do not want an admin
of `Customer A` to also have admin permissions for `Customer B` (to which the user may be linked as a mere ``learner``).
Instead, the ``SystemWideEnterpriseUserRoleAssignment`` model should explicitly record *which* customer
the assigned user has the given role in.

Decisions (interspersed with Consequences)
==========================================

We'll add an ``enterprise_customer`` field to the assignment model
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* It will be an optional field.  It should be a foreign key on ``EnterpriseCustomer.uuid``.
* Via an edx-rbac change, we will also add a boolean ``applies_to_all_contexts`` field,
  which is a wildcard that, if true, indicates the user has the role assigned for every customer.
  It should default to ``false``.
* The semantics of ``applies_to_all_contexts`` imply that ``enterprise_customer`` will sometimes be null.
  For example, a user assigned the ``enterprise_openedx_operator`` role will have ``applies_to_all_contexts``
  set to ``true`` and an ``enterprise_customer`` as ``null``.
* We will add a customer validator to enforce that the ``enterprise_customer`` field can be null
  only when ``applies_to_all_contexts`` is true.

We'll backfill the values of this field
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* We'll make the current, implicit assignments (that is, if a role is assigned to a user, that role
  applies to the user in every customer to which the user is linked) explicit by filling
  in the UUID value of the linked enterprise customer.
* For ``enterprise_openedx_operator`` roles, the ``applies_to_all_contexts`` field will be marked true.

We'll do a hand-audit of enterprise_admin role assignments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* For every user who is effectively an admin of two different enterprise customers,
  we'll have to manually determine (with help from our support team) which of the two customers
  they are actually an admin of, and which they are simply a learner within (unless they're truly an admin of both).

The context of a system-wide enterprise assignment is determined from ``enterprise_customer``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* This is true for every role.
* If ``applies_to_all`` is true, ``get_context()`` should return the wildcard context token "*".
* The code that populates the user JWTs with (role name, customer UUID) pairs shouldn't have to change -
  that code should only be looking at the ``get_context()`` method of the role assignment class.

Admin forms must record a value for ``enterprise_customer``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* It would be nice to "auto-populate" it somehow if the user is linked to only one enterprise customer.

This field will be populated by signal handlers related to enterprise user CRUD operations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Every user will get an ``enterprise_learner`` role assignment for the given enterprise.
* Pending admin "conversion" will result in an ``enterprise_admin`` role assignment for the given enterprise.
* We'll delete the role assignment when an ``EnterpriseCustomerUser`` is deactivated.
