"""
Management command for making things with test factories
"""

import logging
import sys

import factory

from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, SystemCheckError, handle_default_options
from django.db import connections
from django.db.models.fields.related import ForeignKey

# We have to import the enterprise test factories to ensure it's loaded and found by __subclasses__
from test_utils import factories  # pylint: disable=unused-import

# To ensure factories outside of the enterprise package are loaded and found by the script,
# add any additionally desired factories as an import to this file. Make sure to catch the ImportError
# incase other consumers of the command do not have the same factories installed.
# For example:
try:
    import common.djangoapps.student.test.factories  # pylint: disable=unused-import
except ImportError:
    pass

log = logging.getLogger(__name__)


def convert_to_pascal(string):
    """
    helper method to convert strings to Pascal case
    """
    return string.replace("_", " ").title().replace(" ", "")


def pairwise(iterable):
    """
    Convert a list into a list of tuples of adjacent elements.
    s -> [ (s0, s1), (s2, s3), (s4, s5), ... ]
    """
    a = iter(iterable)
    return zip(a, a)


def all_subclasses(cls):
    """
    Recursively get all subclasses of a class
    https://stackoverflow.com/a/3862957
    """
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in all_subclasses(c)])


class Command(BaseCommand):
    """
    Management command for generating Django records from factories with custom attributes

    Example usage:
        $ ./manage.py manufacture_factory_data --model enterprise.models.enterprise_customer \
            --name "Test Enterprise" --slug "test-enterprise"
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            dest='model',
            help='The model for which the record will be written',
        )

    def run_from_argv(self, argv):
        """
        Re-implemented from https://github.com/django/django/blob/main/django/core/management/base.py#L395 in order to
        support individual field customization. We will need to keep this method up to date with our current version of
        Django BaseCommand.

        Uses ``parse_known_args`` instead of ``parse_args`` to not throw an error when encountering unknown arguments

        https://docs.python.org/3.8/library/argparse.html#argparse.ArgumentParser.parse_known_args
        """
        self._called_from_command_line = True
        parser = self.create_parser(argv[0], argv[1])
        options, unknown = parser.parse_known_args(argv[2:])

        # Add the unknowns into the options for use of the handle method
        paired_unknowns = pairwise(unknown)
        field_customizations = {}
        for field, value in paired_unknowns:
            field_customizations[field.strip("--")] = value
        options.field_customizations = field_customizations

        cmd_options = vars(options)
        # Move positional args out of options to mimic legacy optparse
        args = cmd_options.pop("args", ())
        handle_default_options(options)
        try:
            self.execute(*args, **cmd_options)
        except CommandError as e:
            if options.traceback:
                raise

            # SystemCheckError takes care of its own formatting.
            if isinstance(e, SystemCheckError):
                self.stderr.write(str(e), lambda x: x)
            else:
                self.stderr.write("%s: %s" % (e.__class__.__name__, e))
            sys.exit(e.returncode)
        finally:
            try:
                connections.close_all()
            except ImproperlyConfigured:
                # Ignore if connections aren't setup at this point (e.g. no
                # configured settings).
                pass

    def handle(self, *args, **options):
        """
        Entry point for management command execution.
        """
        if not options.get('model'):
            log.error("Did not receive a model")
            raise CommandError("Did not receive a model")

        # Convert to Pascal case if the provided name is snake case/is all lowercase
        path_of_model = options.get('model').split(".")
        if '_' in path_of_model[-1] or path_of_model[-1].islower():
            last_path = convert_to_pascal(path_of_model[-1])
        else:
            last_path = path_of_model[-1]

        provided_model = '.'.join(path_of_model[:-1]) + '.' + last_path
        # Get all installed/imported factories
        factories_list = all_subclasses(factory.django.DjangoModelFactory)
        # Find the factory that matches the provided model
        for potential_factory in factories_list:
            factory_model = potential_factory._meta.model
            if f"{factory_model.__module__}.{factory_model.__name__}" == provided_model:
                packed_factory_kwargs = {}
                field_customizations = options.get('field_customizations')
                # Confirm that the provided custom attributes are valid fields on the provided model
                for field, value in field_customizations.items():
                    stripped_field = field.strip("--")
                    try:
                        f = factory_model._meta.get_field(stripped_field)
                        # Test factories won't accept a FK PK value, we have to supply the object itself.
                        # This also gives us an opportunity to validate that the provided value is a valid.
                        if isinstance(f, ForeignKey):
                            try:
                                related_object = f.related_model.objects.get(pk=value)
                                value = related_object
                            except f.related_model.DoesNotExist:
                                raise CommandError(
                                    f'Could not find record: {value} for model: {stripped_field}'
                                )

                    except FieldDoesNotExist as exc:
                        log.error(f"Provided field: {field} does not exist on {factory_model}")
                        raise CommandError(f'Provided field: {field} does not exist on {factory_model}') from exc
                    # Now that we know the custom attribute exists as a field on the provided model,
                    # add it to the kwargs dictionary for the record generation
                    packed_factory_kwargs[stripped_field] = value

                # Unpack the custom attributes into the kwargs of the factory, generate a record and return the pk
                return str(potential_factory(**packed_factory_kwargs).pk)

        log.error(f"Provided model: {provided_model} does not exist or does not have an associated factory")
        raise CommandError(f"Provided model: {provided_model}'s factory is not imported or does not exist")
