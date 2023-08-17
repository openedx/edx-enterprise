"""
Tests for the Django management command `manufacture data`.
"""

from argparse import _AppendConstAction, _CountAction, _StoreConstAction, _SubParsersAction

import ddt
from pytest import mark

from django.core.management import get_commands, load_command_class
from django.core.management.base import BaseCommand, CommandError
from django.test import TestCase

from enterprise import models


# Copied from django.core.management.__init__.py
# https://github.com/django/django/blob/1ad7761ee616341295f36c80f78b86ff79d5b513/django/core/management/__init__.py#L83
def call_command(command_name, *args, **options):
    """
    Call the given command, with the given options and args/kwargs.

    This is the primary API you should use for calling specific commands.

    `command_name` may be a string or a command object. Using a string is
    preferred unless the command object is required for further processing or
    testing.

    Some examples:
        call_command('migrate')
        call_command('shell', plain=True)
        call_command('sqlmigrate', 'myapp')

        from django.core.management.commands import flush
        cmd = flush.Command()
        call_command(cmd, verbosity=0, interactive=False)
        # Do something with cmd ...
    """
    if isinstance(command_name, BaseCommand):
        # Command object passed in.
        command = command_name
        command_name = command.__class__.__module__.split(".")[-1]
    else:
        # Load the command object by name.
        try:
            app_name = get_commands()[command_name]
        except KeyError:
            raise CommandError("Unknown command: %r" % command_name)  # pylint: disable=raise-missing-from

        if isinstance(app_name, BaseCommand):
            # If the command is already loaded, use it directly.
            command = app_name
        else:
            command = load_command_class(app_name, command_name)

    # Simulate argument parsing to get the option defaults (see #10080 for details).
    parser = command.create_parser("", command_name)
    # Use the `dest` option name from the parser option
    opt_mapping = {
        min(s_opt.option_strings).lstrip("-").replace("-", "_"): s_opt.dest
        for s_opt in parser._actions  # pylint: disable=protected-access
        if s_opt.option_strings
    }
    arg_options = {opt_mapping.get(key, key): value for key, value in options.items()}
    parse_args = []
    for arg in args:
        if isinstance(arg, (list, tuple)):
            parse_args += map(str, arg)
        else:
            parse_args.append(str(arg))

    def get_actions(parser):
        # Parser actions and actions from sub-parser choices.
        for opt in parser._actions:  # pylint: disable=protected-access
            if isinstance(opt, _SubParsersAction):
                for sub_opt in opt.choices.values():
                    yield from get_actions(sub_opt)
            else:
                yield opt

    parser_actions = list(get_actions(parser))
    mutually_exclusive_required_options = {
        opt
        for group in parser._mutually_exclusive_groups  # pylint: disable=protected-access
        for opt in group._group_actions  # pylint: disable=protected-access
        if group.required
    }
    # Any required arguments which are passed in via **options must be passed
    # to parse_args().
    for opt in parser_actions:
        if opt.dest in options and (
            opt.required or opt in mutually_exclusive_required_options
        ):
            opt_dest_count = sum(v == opt.dest for v in opt_mapping.values())
            if opt_dest_count > 1:
                raise TypeError(
                    f"Cannot pass the dest {opt.dest!r} that matches multiple "
                    f"arguments via **options."
                )
            parse_args.append(min(opt.option_strings))
            if isinstance(opt, (_AppendConstAction, _CountAction, _StoreConstAction)):
                continue
            value = arg_options[opt.dest]
            if isinstance(value, (list, tuple)):
                parse_args += map(str, value)
            else:
                parse_args.append(str(value))
    defaults = parser.parse_args(args=parse_args)

    defaults = dict(defaults._get_kwargs(), **arg_options)  # pylint: disable=protected-access
    # Commented out section allows for unknown options to be passed to the command

    # Raise an error if any unknown options were passed.
    # stealth_options = set(command.base_stealth_options + command.stealth_options)
    # dest_parameters = {action.dest for action in parser_actions}
    # valid_options = (dest_parameters | stealth_options).union(opt_mapping)
    # unknown_options = set(options) - valid_options
    # if unknown_options:
    #     raise TypeError(
    #         "Unknown option(s) for %s command: %s. "
    #         "Valid options are: %s."
    #         % (
    #             command_name,
    #             ", ".join(sorted(unknown_options)),
    #             ", ".join(sorted(valid_options)),
    #         )
    #     )
    # Move positional args out of options to mimic legacy optparse
    args = defaults.pop("args", ())
    if "skip_checks" not in options:
        defaults["skip_checks"] = True

    return command.execute(*args, **defaults)


@mark.django_db
@ddt.ddt
class ManufactureDataCommandTests(TestCase):
    """
    Test command `manufacture_data`.
    """
    command = 'manufacture_data'

    def test_single_object_create_no_customizations(self):
        """
        Test that the manufacture_data command will create a single object with no customizations.
        """
        assert models.EnterpriseCustomer.objects.all().count() == 0
        created_object = call_command(self.command, model='enterprise.models.EnterpriseCustomer')
        assert models.EnterpriseCustomer.objects.all().count() == 1
        assert models.EnterpriseCustomer.objects.filter(pk=created_object).exists()

    def test_command_requires_model(self):
        """
        Test that the manufacture_data command will raise an error if no model is provided.
        """
        with self.assertRaises(CommandError):
            call_command(self.command)

    def test_command_requires_valid_model(self):
        """
        Test that the manufacture_data command will raise an error if the provided model is invalid.
        """
        with self.assertRaises(CommandError):
            call_command(self.command, model='enterprise.models.FakeModel')

    def test_command_requires_valid_field(self):
        """
        Test that the manufacture_data command will raise an error if the provided field is invalid.
        """
        with self.assertRaises(CommandError):
            call_command(
                self.command,
                model='enterprise.models.EnterpriseCustomer',
                field_customizations={"fake_field": 'fake_value'}
            )

    def test_command_can_customize_fields(self):
        """
        Test that the manufacture_data command will create a single object with customizations.
        """
        assert models.EnterpriseCustomer.objects.all().count() == 0
        created_object = call_command(
            self.command,
            model='enterprise.models.EnterpriseCustomer',
            field_customizations={'name': 'Test Name'},
        )
        assert models.EnterpriseCustomer.objects.all().count() == 1
        assert models.EnterpriseCustomer.objects.filter(pk=created_object).exists()
        assert models.EnterpriseCustomer.objects.filter(pk=created_object).first().name == 'Test Name'

    def test_command_can_customize_nested_objects(self):
        """
        Test that the manufacture_data command supports customizing nested objects.
        """
        assert models.EnterpriseCustomer.objects.all().count() == 0
        assert models.EnterpriseCustomerUser.objects.all().count() == 0
        created_object = call_command(
            self.command,
            model='enterprise.models.EnterpriseCustomerUser',
            field_customizations={'enterprise_customer__name': 'Test customer'},
        )
        assert models.EnterpriseCustomer.objects.all().count() == 1
        assert models.EnterpriseCustomerUser.objects.all().count() == 1
        assert models.EnterpriseCustomerUser.objects.filter(
            pk=created_object
        ).first().enterprise_customer.name == 'Test customer'
