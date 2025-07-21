"""
Produce a single event for enterprise-specific testing or health checks.

Implements required ``APP.management.commands.*.Command`` structure.
"""
import logging
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand
from enterprise.event_bus import send_enterprise_group_deleted_event

logger = logging.getLogger(__name__)


# First define the topic that our consumer will subscribe to.
ENTERPRISE_CORE_TOPIC = getattr(settings, 'EVENT_BUS_ENTERPRISE_CORE_TOPIC', 'enterprise-core')


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
            send_enterprise_group_deleted_event(group_uuid=str(uuid4()))
        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Error producing Kafka event")
