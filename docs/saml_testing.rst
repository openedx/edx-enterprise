.. _saml-testing-section:

SAML Testing with Keycloak
==========================

edx-enterprise ships a local `Keycloak <https://www.keycloak.org/>`_ setup that
acts as a SAML Identity Provider (IdP) against a devstack LMS.  This lets you
test the full SAML login flow -- including the enterprise TPA pipeline steps --
without an external IdP.

Prerequisites
-------------

* A running `devstack <https://github.com/openedx/devstack>`_ environment with
  the following containers up and running:

  * ``make dev.up.lms+enterprise-catalog+frontend-app-account+frontend-app-authn``

* The edx-enterprise branch you want to test installed as an editable package
  inside the LMS container (``pip install -e /edx/src/edx-enterprise``).

* The following line added to ``/etc/hosts`` on your host machine:

  * ``127.0.0.1 edx.devstack.keycloak``

Starting Keycloak
-----------------

From the **edx-enterprise** repository root:

.. code-block:: bash

   $ make dev.up.keycloak

This starts a Keycloak container (``edx.devstack.keycloak``) on the
devstack Docker network, exposed at ``http://localhost:8080``.

Provisioning
------------

Provisioning configures **both** Keycloak and the LMS in a single step:

.. code-block:: bash

   $ make dev.provision.keycloak

Under the hood this accomplishes the following:

* [Keycloak] Provisions two "realms" within Keycloak, ``gryffindor`` and ``slytherin``, each representing an IdP.

* [Keycloak] Provisions several Keycloak users within those realms.

* [LMS] provisions a SAMLConfiguration record to globally enable SAML auth.

* [LMS] provisions matching LMS records for each of the Keycloak realms:

  * EnterpriseCustomer
  * SAMLProviderConfig + EnterpriseCustomerIdentityProvider (to link the enterprise customer with the Keycloak IdP)
  * EnterpriseCustomerBrandingConfiguration (to give the login/registration pages a distinctive look)
  * User + EnterpriseCustomerUser (to provide LMS-side users corresponding to the IdP side users).

Testing the SAML login flow
----------------------------

1. Navigate to the SAML login URL:

   ``http://localhost:18000/auth/login/tpa-saml/?auth_entry=login&idp=gryffindor``

2. You should be redirected to the Keycloak login page at
   ``http://edx.devstack.keycloak:8080/realms/gryffindor/...``.

3. Log in with the test credentials:

   =========  ======================
   Username   ``gryffindor_learner``
   Password   ``testpass``
   =========  ======================

4. Validate that you were **not** prompted to log into the existing LMS user.
   The ``enterprise_associate_by_email`` pipeline step should discover that the
   pre-provisioned LMS learner is already associated with the SAML-enabled
   enterprise customer, so LMS authentication is skipped.

5. Validate that you have been redirected to the LMS learner dashboard and are
   logged in as ``gryffindor_learner``.  The ``enterprise_associate_by_email``
   step matches the SSO identity to the LMS account by **email**
   (``gryffindor_learner@example.com``); the usernames happening to match here is
   incidental -- association never uses the username.

Testing the SAML disconnect flow
--------------------------------

1. In the same browser session where you completed the SAML login, navigate to
   the Linked Accounts section within the Account MFE:

   http://localhost:1997/#linked-accounts

2. Find the Gryffindor IdP entry and click **Unlink Gryffindor IdP account**.

3. The button should settle into the "unconnected" state with a "Sign in with
   Gryffindor IdP" link. indicating the MFE received a successful
   disconnect response.

Resetting state to repeat tests
-------------------------------

The simplest reset is to re-run idempotent provisioning:

.. code-block:: bash

   $ make dev.provision.keycloak

Stopping Keycloak
-----------------

.. code-block:: bash

   $ make dev.stop.keycloak

The ``keycloak_data`` volume is preserved, so the next ``make dev.up.keycloak``
will resume with the same realm and user data.

Troubleshooting
---------------

**saml --pull fails during provisioning**
   The provisioning script runs ``saml --pull`` to fetch metadata from *all*
   enabled SAML providers.  If a pre-existing ``SAMLProviderConfig`` in your
   devstack points to an unreachable metadata URL, the command will fail.
   Audit the provider list in the LMS Django admin at
   ``http://localhost:18000/admin/third_party_auth/samlproviderconfig/?show_history=1``.

**Browser cannot reach edx.devstack.keycloak**
   Verify the ``/etc/hosts`` entry described above.  If you are using a GitHub
   Codespace or other remote environment, the entry must be on the machine
   running your browser, not inside the remote environment.

**Keycloak admin console**
   The Keycloak admin console is available at
   ``http://edx.devstack.keycloak:8080/admin/master/console/`` with credentials
   ``admin`` / ``admin``.
