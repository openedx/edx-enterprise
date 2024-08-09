Catalog syncing behavior with enterprise-catalog service
------------------------------------------------------------------------------

Status
======

Accepted

Context
=======
We would like to have a way to reuse a saved set of courses configured by a query and use them in multiple catalogs across customers.


Decisions
=========

**Sync catalog/customer data with enterprise-catalog**
As the catalog data is saved in both edx-enterprise and enterprise-catalog, we need to make sure that catalog data is consistent across both.
In the context of edx-enterprise, changes to EnterpriseCatalogQuery and EnterpriseCustomerCatalog will be propagated to their counterparts
in the enterprise-catalog service.


Consequences
============

**EnterpriseCatalogQuery Sync Process**
The enterprise-catalog service enforces a uniqueness constraint for the `content_filter` field, and so edx-enterprise must enforce it as well
or the sync operation will fail and the entities will be out of sync with each other.

In the Django Admin console, whenever a new EnterpriseCatalogQuery is created, or an existing one edited, we first query enterprise-catalog to see if its 
`content_filter` is already in use (by calculating the `content_filter` hash via a call to enterprise-catalog, and then attempting to retrieve
an existing catalog query from enterprise-catalog by that hash).  If the new `content_filter` is unique, we will save the changes and propagate
them to enterprise-catalog. 

If the `content_filter` is *not* unique, we display an error on the EnterpriseCatalogQuery edit page and don't commit the change. 


**EnterpriseCustomerCatalog Sync Process**
In the Django Admin console, whenever a EnterpriseCustomerCatalog is created, or an existing one is edited, we simply pass the changes on to 
enterprise-catalog without doing any checks for duplicates.

When it comes to custom `content_filter` fields attached to EnterpriseCustomerCatalog objects, enterprise-catalog doesn't care if they are 
non-unique, and will simply update the corresponding catalog entity to point to the catalog query that matches the `content_filter`.
