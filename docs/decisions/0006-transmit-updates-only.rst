Transmitting Only Updates IDA
-----------------------------

Status
======

Draft

Context
=======
The transmit_content_metadata jenkins job (along with the underlying integrated_channels.transmit_content_metadata()
task and export() method) makes an uncomfortably large number of calls to the the enterprise-catalog service’s
/api/v1/enterprise-catalog/<uuid>/get_content_metadata endpoint with a relatively low number of customers. The resulting
response payloads are usually quite large which results in the service’s shared Aurora DB often being pinned at 100% CPU
usage and causing a myriad of alerts and warnings.

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

In order to address these performance issues and to more effectively handle on-boarding more customers to the Integrated
Channels, we have decided to address requests to the enterprise catalog on two fronts:

1. Increase the page size of requests going to `/api/v1/enterprise-catalog/<uuid>/get_content_metadata` from a base of
10 to 100. This will reduce the number of calls necessary to retrieve the entire catalog from 150~ to about 15
(as of 07/2021).

2. Add an additional request/check to the Integrated Channel's exporter that will retrieve the last time either a
catalog or the associated content metadata of a catalog has been changed (whichever is most recent). This timestamp will
be compared to the most recent time the customer has had a successful transmission of that particular catalog. If there
is no updated needed, then the exporter will refrain from querying enterprise catalog for the catalog's metadata.

Exceptions
==========

All CSOD customers have been told to expect the cornerstone/course-list endpoint will always return a current state of
the course catalog, meaning that any missing content will be treated as deletes. It is also important to note that
before this ADR, we were not saving any audits of CSOD related transmissions. As such, there are CSOD specific
exemptions to this ADR- specifically we are:

1. adding an export_force_all_catalogs method to the content metadata exporter that effectively functions exactly the
same as the current export method, ignoring updates needed and transmiting all catalogs.

2. adding a new view endpoint `course-updates` that functions exactly as the existing `course-list` except it will
exclude metadata from catalogs that do not require updates.

3. maintaining the existing export behavior in the `course-list` endpoint

4. making create, update and deletes of ContentMetadataItemTransmission objects on all CSOD transmissions the same way
all other channels currently do.

Consequences
============

The transmit-content-metadata jenkins job can continue to run every 10 minutes, so that it catches and transmits updated
content metadata when the metadata actually changes. However, the cost of the average run in terms of CPU usage will go
down significantly. That being said, f any metadata associated with a catalog has changed between job run N and N+1,
then we’ll transmit the full catalog to the integrated channel during run N+1. Typically, the metadata in
enterprise-catalog is updated once per day, so we’d expect to only be transmitting catalog data to these integrated
channels once a day once the proposed change is implemented. Once CSOD customers are informed and agree on a full
feature list of the new `course-updates` endpoint, they will have the same "update only" behavior in their
transmissions. However, it's important to note that CSOD customers are not included in the scheduled
transmit-content-metadata jenkins job and as such, their exclusion from the updated logic will not have a serious
impact.
