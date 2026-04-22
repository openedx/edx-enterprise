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
  the LMS container up.
* The edx-enterprise branch you want to test installed as an editable package
  inside the LMS container (``/edx/src/edx-enterprise``).
* Docker Compose (the ``docker compose`` CLI plugin).

Starting Keycloak
-----------------

From the **edx-enterprise** repository root:

.. code-block:: bash

   $ make dev.up.keycloak

This starts a Keycloak 26.x container (``edx.devstack.keycloak``) on the
devstack Docker network, exposed at ``http://localhost:8080``.  Keycloak data is
persisted in a Docker volume (``keycloak_data``) so the container can be stopped
and restarted without losing state.

Provisioning
------------

Provisioning configures **both** Keycloak and the LMS in a single step:

.. code-block:: bash

   $ make dev.provision.keycloak

Under the hood this runs two commands:

1. ``keycloak-config-cli`` imports the realm definition
   (``keycloak-devstack-realm.json``) into Keycloak, creating a ``devstack``
   realm with a SAML client and a test user.
2. ``provision-tpa.py`` runs inside the LMS container to create the matching
   ``SAMLConfiguration``, ``SAMLProviderConfig``, ``EnterpriseCustomer`` link,
   and a pre-linked LMS learner account.

All shared configuration values (URLs, entity IDs, OIDs, test credentials) live
in ``keycloak-devstack.env`` so the two sides stay in sync.

Host setup
----------

The LMS redirects to Keycloak using the Docker hostname
``edx.devstack.keycloak``.  Your browser needs to resolve that name to
localhost.

Add this line to ``/etc/hosts`` on the machine where your browser runs (your
laptop, **not** a remote codespace):

.. code-block:: text

   127.0.0.1 edx.devstack.keycloak

Testing the SAML login flow
----------------------------

1. Navigate to the SAML login URL:

   ``http://localhost:18000/auth/login/tpa-saml/?auth_entry=login&idp=keycloak-devstack``

2. You should be redirected to the Keycloak login page at
   ``http://edx.devstack.keycloak:8080/realms/devstack/...``.

3. Log in with the test credentials:

   =========  =========================
   Username   ``keycloak_learner``
   Password   ``testpass``
   =========  =========================

4. Validate that you were **not** prompted to log into the existing LMS user.
   The ``enterprise_associate_by_email`` pipeline step should discover that the
   pre-provisioned LMS learner is already associated with the SAML-enabled
   enterprise customer, so LMS authentication is skipped.

5. Validate that you have been redirected to the LMS learner dashboard and are
   logged in as ``keycloak_test_learner``.

Testing the SAML disconnect flow
--------------------------------

Triggering the disconnect via the Account MFE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Bring up the Account MFE container (devstack runs it on port 1997):

   .. code-block:: bash

      $ make dev.up.frontend-app-account

2. In the same browser session where you completed the SAML login, navigate to
   the Linked Accounts section:

   http://localhost:1997/#linked-accounts

3. Find the Keycloak Devstack IdP entry (matches
   SAMLProviderConfig.name) and click **Unlink Keycloak Devstack IdP
   account**.

4. The button should settle into the "unconnected" state with a "Sign in with
   Keycloak Devstack IdP" link. indicating the MFE received a successful
   disconnect response.

Verifying the disconnect
~~~~~~~~~~~~~~~~~~~~~~~~

1. **LMS logs** -- tail the LMS container and grep for the new debug lines:

   .. code-block:: bash

      $ docker logs --tail 500 edx.devstack.lms 2>&1 | grep -E 'SAMLAccountDisconnected|_unlink_enterprise_user_from_idp|successfully unlinked'

   You should see all three lines, in order::

      [THIRD_PARTY_AUTH] Emitting SAMLAccountDisconnected signal for user_id=<id>, backend=tpa-saml
      [ENTERPRISE] _unlink_enterprise_user_from_idp called for user_id=<id>, backend=tpa-saml
      Enterprise learner {keycloak_learner@example.com} successfully unlinked from Enterprise Customer {<name>}

Resetting state to repeat the test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The simplest reset is to re-run provisioning:

.. code-block:: bash

   $ make dev.provision.keycloak

Then navigate to the SAML login URL again to re-link:

   http://localhost:18000/auth/login/tpa-saml/?auth_entry=login&idp=keycloak-devstack

Note: re-running provisioning is necessary because when you clicked the
**Unlink Keycloak Devstack IdP account** button, the SAML disconnect handler
did more than just disconnect from the IdP, it also unlinked the
EnterpriseCustomerUser.  This is only recoverable by an admin or system
operator, hence the need to use the provision script.  Yes, that means in prod
if a learner accidentally clicks the unlink-from-IdP button, they ALSO get
unlinked from the enterprise itself and need to reach out to their admin to get
re-linked to the enterprise.

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
   ``http://localhost:8080/admin/master/console/`` with credentials
   ``admin`` / ``admin``.

**Account MFE shows no linked providers**
    UserSocialAuth likely has no row for this user -- complete the SAML
    login first.
