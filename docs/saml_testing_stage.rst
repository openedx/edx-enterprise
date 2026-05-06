.. _saml-testing-stage-section:

SAML Testing Against Stage with Keycloak
========================================

This is a variant of :ref:`saml-testing-section` that points a **local
Keycloak** at the **remote stage LMS** (``courses.stage.edx.org``) instead of
devstack.  It is useful when you need to validate enterprise TPA pipeline
behavior against real stage data (enterprise customers, learners, feature
flags) without deploying a Keycloak instance somewhere stage can reach.

Network constraints
-------------------

The stage LMS **cannot make API calls to your laptop**, but your laptop **can**
make API calls to stage.  This shapes the whole approach:

* SAML auth itself is browser-mediated, so stage never needs to call Keycloak
  directly during login -- the browser handles every redirect and POST.
* The one place stage normally fetches from the IdP is **metadata**.  Since
  ``saml --pull`` from stage cannot reach ``http://localhost:8080``, you must
  **upload the IdP metadata XML manually** via Django admin (or expose
  Keycloak through a tunnel; see Troubleshooting).
* Your browser must be able to resolve ``edx.devstack.keycloak`` to
  ``localhost``.  This is the same ``/etc/hosts`` requirement as the devstack
  flow.

Prerequisites
-------------

* The edx-enterprise repository on this machine (you do **not** need a running
  devstack LMS; only the Keycloak container is used locally).
* Django admin access to stage (specifically permissions on
  ``third_party_auth.SAMLConfiguration``, ``third_party_auth.SAMLProviderConfig``,
  ``third_party_auth.SAMLProviderData``, ``enterprise.EnterpriseCustomer``,
  ``enterprise.EnterpriseCustomerIdentityProvider``, and the auth user model).
* An existing ``EnterpriseCustomer`` on stage that you control, plus an LMS
  learner account on stage whose **email** matches the Keycloak test user
  (``keycloak_learner@example.com``).  Both are required so
  ``enterprise_associate_by_email`` can match the SAML user during login.
* Docker Compose (the ``docker compose`` CLI plugin).

Stage environment file
----------------------

A pre-built env file ``keycloak-stage.env`` ships in the repository root
alongside ``keycloak-devstack.env``.  It overrides only the SP-side values:

* ``SP_ENTITY_ID=https://courses.stage.edx.org``
* ``ACS_URL=https://courses.stage.edx.org/auth/complete/tpa-saml/``

The Keycloak side still runs locally at
``http://edx.devstack.keycloak:8080`` -- only the SP side moves to stage.
Edit ``keycloak-stage.env`` directly if you need to point at a different
stage host or use different test credentials.

Starting Keycloak
-----------------

The stage flow uses a **separate** Keycloak container
(``edx.local-stage.keycloak``) with its own data volume
(``keycloak_stage_data``).  This keeps the local-stage realm state isolated
from the devstack flow's realm state.

From the **edx-enterprise** repository root:

.. code-block:: bash

   $ make dev.up.keycloak-stage

.. note::

   The two Keycloak containers (``keycloak`` and ``keycloak-stage``) share
   host port ``8080`` and the ``edx.devstack.keycloak`` network alias, so
   only one may run at a time.  Stop the devstack one first if it is
   running:

   .. code-block:: bash

      $ make dev.stop.keycloak

   Run ``make dev.stop.keycloak-stage`` later when you are done; the
   ``keycloak_stage_data`` volume is preserved across restarts.

Provisioning Keycloak for stage
-------------------------------

.. code-block:: bash

   $ make dev.provision.keycloak-stage

This imports the ``local-stage`` realm (named via ``REALM_NAME`` in
``keycloak-stage.env``) into the stage Keycloak container, configuring the
SAML client with stage's entity ID and ACS URL.  The realm definition
(``keycloak-devstack-realm.json``) is shared with the devstack flow -- only
the env-substituted values differ.

Unlike ``make dev.provision.keycloak``, this target does **not** run
``provision-tpa.py`` -- there is no local LMS container to provision and
``provision-tpa.py`` would not be appropriate against stage anyway.  The
target prints a reminder pointing at the manual stage-admin steps below.

Host setup
----------

Add this line to ``/etc/hosts`` on the machine where your browser runs:

.. code-block:: text

   127.0.0.1 edx.devstack.keycloak

This is the same entry used by the devstack flow.  Stage redirects your
browser to ``http://edx.devstack.keycloak:8080/...`` for SAML login, and your
browser needs to resolve that name to localhost.

Configure stage via Django admin
--------------------------------

Because you cannot run ``provision-tpa.py`` against stage, do the equivalent
configuration manually through the stage admin.

1. **SAMLConfiguration** (https://internal.courses.stage.edx.org/admin/third_party_auth/samlconfiguration/)

   Create a new version (or confirm an existing one) with:

   * site = current site
   * slug = ``default``
   * enabled = checked
   * entity_id = ``https://courses.stage.edx.org`` (must match
     ``SP_ENTITY_ID`` in ``keycloak-stage.env`` — note this is the public
     host, not the internal admin host)

2. **Fetch IdP metadata XML from local Keycloak**

   In a terminal on your laptop:

   .. code-block:: bash

      $ curl -s http://edx.devstack.keycloak:8080/realms/local-stage/protocol/saml/descriptor > keycloak-stage-metadata.xml

   This XML is the IdP's self-description -- entity ID, SSO URL, signing
   certificate.  Stage cannot fetch this URL itself, so you upload the XML
   directly in the next step.

3. **SAMLProviderConfig** (https://internal.courses.stage.edx.org/admin/third_party_auth/samlproviderconfig/)

   Add a new provider with:

   * slug = ``keycloak-stage`` (any unique slug; the resulting provider_id will
     be ``saml-keycloak-stage``)
   * name = ``Keycloak Stage IdP``
   * entity_id = ``http://edx.devstack.keycloak:8080/realms/local-stage``
   * enabled = checked
   * visible = checked
   * skip_registration_form = checked
   * skip_email_verification = checked
   * send_to_registration_first = checked
   * **User ID Attribute** (``attr_user_permanent_id``) = ``urn:oid:0.9.2342.19200300.100.1.3``
   * **Email Attribute** (``attr_email``) = ``urn:oid:0.9.2342.19200300.100.1.3``
   * **First Name Attribute** (``attr_first_name``) = ``urn:oid:2.5.4.42``
   * **Last Name Attribute** (``attr_last_name``) = ``urn:oid:2.5.4.4``
   * **metadata_source**: leave blank, OR set to a placeholder that you know
     stage cannot reach.  Either way, do **not** rely on ``saml --pull``.

4. **SAMLProviderData** (https://internal.courses.stage.edx.org/admin/third_party_auth/samlproviderdata/)

   This is the row that ``saml --pull`` would normally populate from the
   metadata URL.  Since stage cannot reach Keycloak, create the row by hand
   from the XML you fetched in step 2:

   * entity_id = ``http://edx.devstack.keycloak:8080/realms/local-stage``
   * sso_url = ``http://edx.devstack.keycloak:8080/realms/local-stage/protocol/saml``
     (or whatever ``<SingleSignOnService Location="...">`` shows in the XML)
   * public_key = base64-encoded cert from the
     ``<X509Certificate>`` element in the XML (whitespace stripped)
   * fetched_at = now
   * expires_at = a far-future timestamp

5. **EnterpriseCustomerIdentityProvider** (https://internal.courses.stage.edx.org/admin/enterprise/enterprisecustomeridentityprovider/)

   Link the SAML provider to your enterprise customer:

   * provider_id = ``saml-keycloak-stage`` (matches the slug from step 3,
     prefixed with ``saml-``)
   * enterprise_customer = the customer you are testing with

6. **Pre-link an LMS learner**

   Confirm an LMS learner exists on stage with email
   ``keycloak_learner@example.com`` and is linked to the enterprise customer
   via ``EnterpriseCustomerUser``.  Create both rows if needed.

Testing the SAML login flow
---------------------------

1. Navigate to the stage SAML login URL:

   ``https://courses.stage.edx.org/auth/login/tpa-saml/?auth_entry=login&idp=keycloak-stage``

2. You should be redirected to the Keycloak login page at
   ``http://edx.devstack.keycloak:8080/realms/local-stage/...``.

3. Log in with the test credentials:

   =========  =========================
   Username   ``keycloak_learner``
   Password   ``testpass``
   =========  =========================

4. Validate that you were **not** prompted to log into the existing LMS user.
   The ``enterprise_associate_by_email`` pipeline step should discover that
   the pre-provisioned stage learner is already associated with the
   SAML-enabled enterprise customer, so LMS authentication is skipped.

5. Validate that you have been redirected to the stage learner dashboard and
   are logged in as the pre-linked learner.

Testing the SAML disconnect flow
--------------------------------

The stage Account MFE is at ``https://account.stage.edx.org/``.  The flow is
identical to the devstack version:

1. In the same browser session where you completed the SAML login, navigate
   to the Linked Accounts page:

   https://account.stage.edx.org/#linked-accounts

2. Find the ``Keycloak Stage IdP`` entry and click **Unlink Keycloak
   Stage IdP account**.

3. The button should settle into the "unconnected" state with a "Sign in
   with Keycloak Stage IdP" link.

You will not be able to ``docker logs`` the stage LMS, so the verification
steps from the devstack doc do not apply directly.  Use stage Splunk / log
aggregation to look for the same log lines:

.. code-block:: text

   [THIRD_PARTY_AUTH] Emitting SAMLAccountDisconnected signal for user_id=<id>, backend=tpa-saml
   [ENTERPRISE] _unlink_enterprise_user_from_idp called for user_id=<id>, backend=tpa-saml
   Enterprise learner {keycloak_learner@example.com} successfully unlinked from Enterprise Customer {<name>}

Resetting state to repeat the test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There is no equivalent of ``make dev.provision.keycloak`` for stage.  To
re-link after a disconnect:

* Re-create the ``EnterpriseCustomerUser`` row in stage admin (the unlink
  flow deletes it).
* Then visit the SAML login URL again to re-link the social auth row.

Stopping Keycloak
-----------------

.. code-block:: bash

   $ make dev.stop.keycloak-stage

The ``keycloak_stage_data`` volume is preserved.  The next
``make dev.up.keycloak-stage`` will resume with the same realm and SAML
client config -- no need to re-run ``make dev.provision.keycloak-stage``
unless you want to reset the realm.

Troubleshooting
---------------

**Stage cannot validate the SAML response**
   Stage uses the cert it has cached in ``SAMLProviderData.public_key`` to
   verify Keycloak's signature.  If you regenerate the realm keys (or
   re-import a realm with different keys), re-fetch the metadata XML and
   update the ``public_key`` row in stage admin.

**"No SAMLProviderData found" or signature errors after re-import**
   Same fix -- the IdP signing key has rotated.  Pull fresh metadata from
   ``http://edx.devstack.keycloak:8080/realms/local-stage/protocol/saml/descriptor``
   and update ``SAMLProviderData`` on stage.

**Browser cannot reach edx.devstack.keycloak**
   Verify the ``/etc/hosts`` entry described above.  Unlike the devstack
   flow, you cannot work around this from a remote codespace -- the browser
   itself must resolve ``edx.devstack.keycloak`` to ``127.0.0.1`` and reach
   your laptop's port 8080.

**Stage admin will not let me leave metadata_source blank**
   If the field is required, set it to a clearly-fake value such as
   ``http://edx.devstack.keycloak.invalid/...``.  Just make sure no
   ``saml --pull`` job runs on stage against this provider; if one does, it
   will fail and may invalidate other providers' data depending on the
   ``saml`` command's error handling.

**Alternative: expose Keycloak via a tunnel**
   If manual ``SAMLProviderData`` upkeep is too painful, expose your local
   Keycloak with a tunnel (``ngrok``, ``cloudflared``) so stage can reach it.
   You then set ``metadata_source`` to the tunnel URL and let
   ``saml --pull`` work normally.  Note that the tunnel hostname becomes
   part of the IdP entity ID, so you must rebuild the realm with that
   hostname in ``KEYCLOAK_URL`` -- and any existing
   ``UserSocialAuth`` rows tied to the old entity ID will not match.

**Keycloak admin console**
   Available at ``http://localhost:8080/admin/master/console/`` with
   credentials ``admin`` / ``admin``.  Use this to inspect the SAML client
   config after a stage-env import to confirm Client ID and ACS URL match
   stage.
