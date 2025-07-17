"""
Produce a single event for enterprise-specific testing or health checks.

Implements required ``APP.management.commands.*.Command`` structure.
"""
import logging
import uuid

import attr
from django.conf import settings
from django.core.management.base import BaseCommand
from edx_event_bus_kafka.internal.producer import create_producer
from openedx_events.data import EventsMetadata
from openedx_events.tooling import OpenEdxPublicSignal

logger = logging.getLogger(__name__)


# First define the topic that our consumer will subscribe to.
ENTERPRISE_CORE_TOPIC = getattr(settings, 'EVENT_BUS_ENTERPRISE_CORE_TOPIC', 'enterprise-core')


# Define the shape/schema of the data that our consumer will process.
# It should be identical to the schema used to *produce* the event.
@attr.s(frozen=True)
class PingData:
    """
    Attributes of a ping record.
    """
    ping_uuid = attr.ib(type=str)
    ping_message = attr.ib(type=str)


ENTERPRISE_PING_DATA_SCHEMA = {
    "ping": PingData,
}

# Define the key field used to serialize and de-serialize the event data.
ENTERPRISE_PING_KEY_FIELD = 'ping.ping_uuid'

# Define a Signal with the type (unique name) of the event to process,
# and tell it about the expected schema of event data. The producer of our ping events
# should emit an identical signal (same event_type and data schema).
ENTERPRISE_PING_SIGNAL = OpenEdxPublicSignal(
    event_type="org.openedx.enterprise.core.ping.v1",
    data=ENTERPRISE_PING_DATA_SCHEMA
)


def ping_event_data():
    """
    Helper to produce a dictionary of ping event data
    that fits the schema defined above by ``PingData`` and the
    ``data`` expected by our Ping Signal.
    """
    return {
        'ping': {
            'ping_uuid': str(uuid.uuid4()),
            'ping_message': 'hello, world',
        }
    }


class Command(BaseCommand):
    """
    Management command to produce a test event to the event bus.
    """
    help = """
    Produce a single ping event to the configured test topic.

    example:
        ./manage.py produce_enterprise_ping_event
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--topic', nargs=1, required=False,
            help="Optional topic to produce to (without environment prefix)",
        )

    def handle(self, *args, **options):
        try:
            producer = create_producer()
            producer.send(
                signal=ENTERPRISE_PING_SIGNAL,
                topic=ENTERPRISE_CORE_TOPIC,
                event_key_field=ENTERPRISE_PING_KEY_FIELD,
                event_data=ping_event_data(),
                event_metadata=EventsMetadata(
                    event_type=ENTERPRISE_PING_SIGNAL.event_type,
                ),
            )
            producer.prepare_for_shutdown()  # otherwise command may exit before delivery is complete
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Error producing Kafka event")
