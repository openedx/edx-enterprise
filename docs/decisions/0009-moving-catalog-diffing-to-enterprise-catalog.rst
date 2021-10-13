Moving the responsibility of catalog diffing to the enterprise catalog
----------------------------------------------------------------------

Status
======

Draft

Context
=======

Recent, now reverted, attempts to make efficiency improvements to the integrated channels requesting data from the
enterprise catalogs have highlighted short comings of the current architecture in terms of the capabilities of the
Integrated Channels to accurately report the last time a customer's full catalog has been successfully updated. Because
the Integrated Channels are responsible for chunking transmissions (only sending as much as the individual channel's API
allows at a given time) such that not all content under a customer's catalog is guaranteed to be transmitted in a single
scheduled run, we cannot accurately determine if all content under a customer's catalog has been updated since the
catalog has last updated without first using the enterprise catalog's currently available API `get_content_metadata`
endpoint.

Consequences
============

**querying all content from the catalog service is expensive**- Asking for all content under the catalog, for every
customer, for every catalog, on every transmission is not only an undesirably large request to be sending, but also
consumes much of the enterprise catalog's DB load. We need a smarter solution to how the Integrated Channels requests
content from the catalog service.

**putting the responsibility of determining differences** between what's already been sent to the customers and what's
currently in customer's catalogs adds much complexity to the integrated channels which can make it unapproachable from
an onboarding perspective but also from a debugging point of view. Log noise and number of potential error sources means
tracking down issues within the Integrated Channels are costly and time consuming.

How do the Integrated Channels currently handle customer catalog data?
======================================================================

existing flow chart:

.. image:: ../images/0009-moving-catalog-diffing-to-enterprise-catalog.rst
  :width: 500

Currently on a scheduled job, the Integrated Channels' content metadata exporter iterates over each customer's catalog
and builds up a dict of content representing the current state of the customer's catalog content. Take away- as it
stands now, the Integrated Channels assumes that the content metadata exporter will report the entirety of the
customer's purchased content, then pass that payload to the content metadata transmitter which compares the payload with
all saved `ContentMetadataItemTransmission` items under the customer to determine which items it (the transmitter) needs
to create, update, and delete. It then chunks up each of the buckets, and sends those chunks (up to a limited number of
times) to the client to send to the customer's LMS and saves the updated `ContentMetadataItemTransmission` entry.

How the Integrated Channels could better determine if customer metadata needs updating
======================================================================================

proposed flow chart:

.. image:: ../images/new-integrated-channels-metadata-flow.png
  :width: 500

If we build an endpoint that takes catalog UUIDs and a set of content keys linked to the uuid and returns three buckets
of data:

1) What content keys exist under the specified catalog that were not provided in the list of content keys

2) What content keys don't exist under the specified catalog that were provided in the list of content keys

3) What the last updated at times of the content keys are for the content keys provided that are under the specified
catalog

We would be able to move the responsibility of diffing what the customer has with what the customer should have to the
enterprise catalog. This would mean that the only job of the Integrated Channels would be to compare the last updated
times of the courses that already exist to get which courses need updates. Creates and deletes would already determined
by the first endpoint.

Further Improvements
====================

There are two additional improvements to explore with the Integrated Channels' metadata transmission flow. Firstly,
we remove records from our transmission audit table when a delete request is issued. This can result in `lost` nodes of
content (as we've actively seen from customers) where content can be assumed to be deleted on our end but have it exist
still on the customer's external LMS. The fix here is pretty easy- if we choose to not delete records, but rather create
a new, nullable `deleted_at` or equivalent field in the transmission record table. Then we would be able to mark and
exclude any deleted records from appropriate look ups, but still have something to help us identify past courses that
were sent to customers.

As stated earlier, currently the only method to retrieve content under a customer's catalog is the singular, bulk
`get_content_metadata` endpoint. This returns all content metadata belonging to an enterprise catalog. If we were to
build out the existing endpoint where individual content key's worth of metadata could be specified in the request body,
then we would be able to further reduce the amount the Integrated Channels request unused data.


