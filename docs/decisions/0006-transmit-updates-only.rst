Transmitting Only Updates IDA
-----------------------------

Status
======

Draft

Context
=======
The transmit_content_metadata jenkins job (along with the underlying integrated_channels.transmit_content_metadata()
task and export() method) makes an uncomfortably large number of calls to the the enterprise-catalog service’s
/api/v1/enterprise-catalog/<uuid>/get_content_metadata endpoint with a relatively low number of customers which results
in an unacceptably high database load.

At the same time the data being requested by this frequently-running job is often unchanged between runs - content
metadata tends to change in enterprise-catalog roughly once/day.

Our main goals are as follows:

1. Reduce the overall number of calls required by the Integrated Channels in order to retrieve the content metadata for
any particular transmission.

2. Prevent the Integrated Channels from making an abundance of requests to the enterprise catalog if there is no update
needed (ie if nothing in the catalog has changed)

What is the transmit_content_metadata job and underlying export method?
_______________________________________________________________________

transmit_content_metadata is one of the three core tasks of the Integrated Channels, the other two being
transmit_learner_data and transmit_subsection_learner_data. Specifically transmit_content_metadata's job is to gather
course metadata contained within the customer's enterprise catalog and transmit create, update and deletes of course
entities, through customer configurations, to the external LMS'.

The `export()` method is the main method responsible for fetching said content metadata. It will take all listed
`catalogs to transmit` under the customer's configurations (otherwise will default to all the customer's catalogs if
`catalogs to transmit` is not provided) and request content metadata from the enterprise catalog. These catalogs can
range from "all possible content" to a specific, single course.

Decisions
=========

In order to address these performance issues and to more effectively handle onboarding more customers to the Integrated
Channels, we have decided to address requests to the enterprise catalog on two fronts:

1. Increase the page size of requests going to `/api/v1/enterprise-catalog/<uuid>/get_content_metadata` from a base of
10 to 100. This will reduce the number of calls necessary to retrieve the entire catalog from 150~ to about 15
(as of 07/2021).

2. Add an additional request/check to the Integrated Channel's exporter that will retrieve the last time either a
catalog or the associated content metadata of a catalog has been changed (whichever is most recent). This timestamp will
be compared to the `content_last_changed` field of the ContentMetadataItemTransmission object, which is the `catalog
last modified` value retrieved from the customer's most recent successful transmission. If there
is no updated needed, then the exporter will refrain from querying enterprise catalog for the catalog's metadata.

Exceptions
==========

1. The Cornerstone (CSOD) LMS Integration will not use the 'transmit only updates' rule."

2. CSOD related transmissions will record ContentMetadataItemTransmission objects, same as all other channels.

Consequences
============

The transmit-content-metadata jenkins job can continue to run on a frequent schedule without having to worry about
unacceptably large database loads, as it will record when updates are needed and will only request data when necessary.
If any metadata associated with a catalog has changed between job run N and N+1, then we’ll transmit the full catalog to
the integrated channel during run N+1. It should be noted that there could be potential further improvements to the
entire export process, as currently we are requesting the entire catalog and not only updated content. Reducing requests
to only the updated metadata could further reduce database loads.
