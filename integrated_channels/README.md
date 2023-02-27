# Integrated Channels

## Overview

An integrated channel is an abstraction meant to represent a third-party system
which provides an API that can be used to transmit EdX data to the third-party
system. The most common example of such a third-party system is an enterprise-level
learning management system (LMS). LMS users are able to discover content made available
by many different content providers and manage the learning outcomes that are produced
by interaction with the content providers. In such a scenario, EdX would be the content
provider while a system like SAP SuccessFactors would be the integrated channel.

The integrated channel subsystem was developed as a means for consolidating common code
needed for integrating the EdX ecosystem with any integrated channel and minimizing the
amount of code that would need to be written in order to add a new integrated channel.

## Integration Phases

The subsystem organizes the integration into two separate phases:

1. The *export* phase is where data is collected from the EdX ecosystem
   and transformed into the schema expected by the integrated channel.
2. The *transmission* phase is where the exported data is transmitted to
   the integrated channel by whatever means is provided by the third-party
   system, usually an HTTP-based API. 

There are [base implementations](https://github.com/openedx/edx-enterprise/tree/master/integrated_channels/integrated_channel)
for each of these phases which can be extended for
channel-specific customizations needed for integrating with a given integrated channel.
Channel-specific implementation code should be placed in a new directory adjacent to
the base implementation code.

For example:

* [degreed](https://github.com/openedx/edx-enterprise/tree/master/integrated_channels/degreed)
* [sap_success_factors](https://github.com/openedx/edx-enterprise/tree/master/integrated_channels/sap_success_factors)

## Integration Points

There are currently two integration points supported for integrated channels:

1. *Content metadata* - Metadata (e.g. titles, descriptions, etc.) related to EdX content (e.g.     courses, programs) can be exported and transmitted to an integrated channel to assist content    discovery in the third-party system.
2. *Learner data* - Specifically, learner outcome data for each content enrollment can be
   exported and transmitted to the integrated channel.

Additional integration points may be added in the future.

## Integrated Channel Configuration

There is a many-to-many relationship between integrated channels and enterprise customers.
Configuration information related to an enterprise-specific integrated channel is stored in
the database by creating a concrete implementation of the abstract
[EnterpriseCustomerPluginConfiguration](https://github.com/openedx/edx-enterprise/blob/master/integrated_channels/integrated_channel/models.py) model. Fields can be added to the concrete
implementation to store values such as the API credentials for a given enterprise customer's
instance of an integrated channel.

Configuration that is common for all instances of integrated channel regardless of enterprise
customer should be persisted by implementing a model within the channel-specific implementation
directory, (e.g. [SAPSuccessFactorsGlobalConfiguration](https://github.com/openedx/edx-enterprise/blob/master/integrated_channels/sap_success_factors/models.py)).

## Content Metadata Synchronization

The set of content metadata transmitted for a given integrated channel instance is defined by the
EnterpriseCustomerCatalogs configured for the associated EnterpriseCustomer. In order to ensure that the content metadata transmitted to an integrated channel is synchronized with the content made available by the EnterpriseCustomer's catalogs, each content metadata item transmission is persisted using the [ContentMetadataItemTransmission](https://github.com/openedx/edx-enterprise/blob/master/integrated_channels/integrated_channel/models.py) model. ContentMetadataItemTransmission records are created, updated, and deleted as EnterpriseCustomerCatalogs are modified and modified sets of content metadata are exported and transmitted to the integrated channel.

## Implementing a new Integrated Channel

Here is the general implementation plan for creating a new integrated channel.

1. Obtain API documentation for the third-party service which the integrated
   channel will represent.
2. Implement a concrete subclass of [IntegratedChannelApiClient](https://github.com/openedx/edx-enterprise/blob/master/integrated_channels/integrated_channel/client.py).
3. Copy/paste one of the existing integrated channel directories and modify the implementation
   as needed for the new integrated channel.
