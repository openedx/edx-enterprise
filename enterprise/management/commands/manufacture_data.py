"""
Management command for making things with test factories
"""

import logging
import sys

import factory
from factory.declarations import SubFactory

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError, SystemCheckError, handle_default_options
from django.db import connections

from enterprise.utils import convert_to_snake

# We have to import the enterprise test factories to ensure it's loaded and found by __subclasses__
# To ensure factories outside of the enterprise package are loaded and found by the script,
# add any additionally desired factories as an import to this file. Make sure to catch the ImportError
# incase other consumers of the command do not have the same factories installed.
# For example:
try:
    import common.djangoapps.student.tests.factories  # pylint: disable=unused-import

    from test_utils import factories  # pylint: disable=unused-import
except ImportError:
    pass

log = logging.getLogger(__name__)


def convert_to_pascal(string):
    """
    helper method to convert strings to Pascal case.
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


class Node():
    """
    Non-binary tree node class for building out a dependency tree of objects to create with customizations.
    """
    def __init__(self, data):
        self.data = data
        self.children = []
        self.customizations = {}
        self.factory = None
        self.instance = None

    def set_single_customization(self, field, value):
        """
        Set a single customization value to the current node, overrides existing values under the same key.
        """
        self.customizations[field] = value

    def add_child(self, obj):
        """
        Add a child to the current node
        """
        self.children.append(obj)

    def find_value(self, value):
        """
        Find a value in the tree
        """
        if self.data == value:
            return self
        else:
            for child in self.children:
                found = child.find_value(value)
                if found:
                    return found
            return None

    def build_records(self):
        """
        Recursively build out the tree of objects by first dealing with children nodes before getting to the parent.
        """
        built_children = {}
        for child in self.children:
            # if we have an instance, use it instead of creating more objects
            if child.instance:
                built_children.update({convert_to_snake(child.data): child.instance})
            else:
                # Use the output of child ``build_records`` to create the current level.
                built_child = child.build_records()
                built_children.update(built_child)

        # The data factory kwargs are specified custom fields + the PK's of generated child objects
        object_fields = self.customizations.copy()
        object_fields.update(built_children)

        # Some edge case sanity checking
        if not self.factory:
            raise CommandError(f"Cannot build objects as {self} does not have a factory")

        built_object = self.factory(**object_fields)
        object_data = {convert_to_snake(self.data): built_object}
        return object_data

    def __str__(self, level=0):
        """
        Overridden str method to allow for proper tree printing
        """
        if self.instance:
            body = f"PK: {self.instance.pk}"
        else:
            body = f"fields: {self.customizations}"
        ret = ("\t" * level) + f"{repr(self.data)} {body}" + "\n"
        for child in self.children:
            ret += child.__str__(level + 1)
        return ret

    def __repr__(self):
        """
        Overridden repr
        """
        return f'<Tree Node {self.data}>'


def build_tree_from_field_list(list_of_fields, provided_factory, base_node, customization_value):
    """
    Builds a non-binary tree of nodes based on a list of children nodes, using a base node and it's associated data
    factory as the parent node the user provided value as a reference to a potential, existing record.

    - list_of_fields (list of strings): the linked list of associated objects to create. Example-
        ['enterprise_customer_user', 'enterprise_customer', 'site']
    - provided_factory (factory.django.DjangoModelFactory): The data factory of the base_node.
    - base_node (Node): The parent node of the desired tree to build.
    - customization_value (string): The value to be assigned to the object associated with the last value in the
        ``list_of_fields`` param. Can either be a FK if the last value is a subfactory, or alternatively
        a custom value to be assigned to the field. Example-
        list_of_fields = ['enterprise_customer_user', 'enterprise_customer', 'site'],
        customization_value = 9
        or
        list_of_fields = ['enterprise_customer_user', 'enterprise_customer', 'name'],
        customization_value = "FRED"
    """
    current_factory = provided_factory
    current_node = base_node
    for index, value in enumerate(list_of_fields):
        try:
            # First we need to figure out if the current field is a sub factory or not
            f = getattr(current_factory, value)
            if isinstance(f, SubFactory):
                fk_object = None
                f_model = f.get_factory()._meta.get_model_class()

                # if we're at the end of the list
                if index == len(list_of_fields) - 1:
                    # verify that the provided customization value is a valid pk for the model
                    try:
                        fk_object = f_model.objects.get(pk=customization_value)
                    except f_model.DoesNotExist as exc:
                        raise CommandError(
                            f"Provided FK value: {customization_value} does not exist on {f_model.__name__}"
                        ) from exc

                # Look for the node in the tree
                if node := current_node.find_value(f_model.__name__):
                    # Not supporting customizations and FK's
                    if (bool(node.customizations) or bool(node.children)) and bool(fk_object):
                        raise CommandError("This script does not support customizing provided existing objects")
                    # If we found the valid FK earlier, assign it to the node
                    if fk_object:
                        node.instance = fk_object
                    # Add the field to the children of the current node
                    if node not in current_node.children:
                        current_node.add_child(node)
                    # Set current node and move on
                    current_node = node
                else:
                    # Create a new node
                    node = Node(
                        f_model.__name__,
                    )
                    node.factory = f.get_factory()
                    # If we found the valid FK earlier, assign it to the node
                    if fk_object:
                        node.instance = fk_object
                    # Add the field to the children of the current node
                    current_node.add_child(node)

                current_node = node
                current_factory = f.get_factory()
            else:
                if current_node.instance:
                    raise CommandError("This script cannot modify existing objects")
                current_node.set_single_customization(value, customization_value)
        except AttributeError as exc:
            log.error(f'Could not find value: {value} in factory: {current_factory}')
            raise CommandError(f'Could not find value: {value} in factory: {current_factory}') from exc
    return base_node


class Command(BaseCommand):
    """
    Management command for generating Django records from factories with custom attributes

    Example usage:
        $ ./manage.py manufacture_data --model enterprise.models.enterprise_customer \
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
            # Fetch the model for the factory
            factory_model = potential_factory._meta.model
            # Check if the factories model matches the provided model
            if f"{factory_model.__module__}.{factory_model.__name__}" == provided_model:
                # Now that we have the right factory, we can build according to the provided custom attributes
                field_customizations = options.get('field_customizations', {})
                base_node = Node(factory_model.__name__)
                base_node.factory = potential_factory
                # For each provided custom attribute...
                for field, value in field_customizations.items():

                    # We need to build a tree of objects to be created and may be customized by other custom attributes
                    stripped_field = field.strip("--")
                    fk_field_customization_split = stripped_field.split("__")
                    base_node = build_tree_from_field_list(
                        fk_field_customization_split,
                        potential_factory,
                        base_node,
                        value,
                    )

                built_node = base_node.build_records()
                log.info(f"\nGenerated factory data: \n{base_node}")
                return str(list(built_node.values())[0].pk)

        log.error(f"Provided model: {provided_model} does not exist or does not have an associated factory")
        raise CommandError(f"Provided model: {provided_model}'s factory is not imported or does not exist")
