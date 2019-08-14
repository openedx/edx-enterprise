# -*- coding: utf-8 -*-
"""
Tests for the `edx-enterprise` admin actions module.
"""
from __future__ import absolute_import, unicode_literals

import unittest

import factory
import mock
import unicodecsv
from pytest import mark
from six import BytesIO

from enterprise.admin import EnterpriseCustomerAdmin
from enterprise.admin.actions import export_as_csv_action
from test_utils.factories import EnterpriseCustomerFactory, EnterpriseCustomerIdentityProviderFactory


class DummyModel(object):
    """
    Dummy "model" for action testing purposes.
    """
    def __init__(self, code, name, description="description"):
        self.code = code
        self.name = name
        self.description = description

    def greeting(self):
        """
        Dummy method to test exporting callable.
        """
        return "Hi, {name}".format(name=self.name)


class DummyFactory(factory.Factory):
    """
    Factoryboy factory for Dummy model.
    """

    class Meta(object):
        model = DummyModel

    code = 1
    name = "dummy 1"
    description = "description"


@mark.django_db
class TestCSVExportAction(unittest.TestCase):
    """
    Tests for csv_export_action.
    """
    def _make_patch(self, target, **kwargs):
        """
        Patch `target` with mock for the duration of test run.
        """
        target_mock = mock.Mock(**kwargs)
        patch = mock.patch(target, new=target_mock)

        patch.start()
        self.addCleanup(patch.stop)
        return target_mock

    def _make_field(self, name):
        """
        Mock django field.
        """
        field = mock.Mock()
        field.name = name
        return field

    def _assert_correct_csv(self, actual_csv, expected_rows):
        """
        Asserts that CSV file ``actual_csv`` contains ``expected_rows``
        """
        reader = unicodecsv.reader(actual_csv.getvalue().splitlines(), encoding="utf-8")
        # preprocess expected - convert everything to strings
        expected_rows = [
            [str(item) for item in row]
            for row in expected_rows
        ]
        actual_rows = list(reader)
        self.assertEqual(actual_rows, expected_rows)

    def setUp(self):
        """
        Test suite set up method.
        """
        super(TestCSVExportAction, self).setUp()
        self.output_stream = BytesIO()
        response_instance_mock = mock.MagicMock(wraps=self.output_stream)
        self.response_mock = self._make_patch(
            "enterprise.admin.actions.HttpResponse",
            return_value=response_instance_mock
        )

        self.model_admin_mock = mock.Mock()
        self.model_admin_mock.model._meta.fields = [
            self._make_field("code"), self._make_field("name"), self._make_field("description"),
        ]

    def test_export_as_csv_defaults(self):
        """
        Test export_as_csv with default values: export all model fields, output headers.
        """
        fields = ["code", "name", "description"]
        collection = [
            DummyFactory(code=1, name="dummy 1"),
            DummyFactory(code=2, name="dummy 2"),
            DummyFactory(code=3, name="dummy 3", description="new description"),
        ]

        export_as_csv = export_as_csv_action()

        expected_rows = [
            fields,
            [1, "dummy 1", "description"],
            [2, "dummy 2", "description"],
            [3, "dummy 3", "new description"],
        ]

        export_as_csv(self.model_admin_mock, mock.Mock(), collection)

        self.response_mock.assert_called_once_with(content_type="text/csv")

        self._assert_correct_csv(self.output_stream, expected_rows)

    def test_export_as_csv_some_fields(self):
        """
        Test export_as_csv with customized fields: export some model fields, output headers.
        """
        fields = ["code", "name"]
        collection = [
            DummyFactory(code=1, name="dummy 1"),
            DummyFactory(code=2, name="dummy 2"),
        ]

        export_as_csv = export_as_csv_action(fields=fields)

        expected_rows = [
            fields,
            [1, "dummy 1"],
            [2, "dummy 2"],
        ]

        export_as_csv(self.model_admin_mock, mock.Mock(), collection)
        self._assert_correct_csv(self.output_stream, expected_rows)

    def test_export_as_csv_callable_fields(self):
        """
        Test export_as_csv - some fields are callables.
        """
        expected_fields = ["code", "name", "greeting"]
        collection = [
            DummyFactory(code=1, name="dummy 1"),
            DummyFactory(code=2, name="dummy 2"),
        ]

        self.model_admin_mock.model._meta.fields.append(self._make_field("greeting"))
        export_as_csv = export_as_csv_action(fields=expected_fields)

        expected_rows = [
            expected_fields,
            [1, "dummy 1", "Hi, dummy 1"],
            [2, "dummy 2", "Hi, dummy 2"],
        ]

        export_as_csv(self.model_admin_mock, mock.Mock(), collection)
        self._assert_correct_csv(self.output_stream, expected_rows)

    def test_export_as_csv_special(self):
        """
        Test export_as_csv - test special case handling.

        Special cases are None and empty string values - they are substituted by [markers] for slightly better
        appearance.
        """
        fields = ["code", "name"]
        collection = [
            DummyFactory(code=1, name=None),
            DummyFactory(code=2, name=""),
            DummyFactory(code=0, name="QWERTY"),
        ]

        export_as_csv = export_as_csv_action(fields=fields)
        expected_rows = [
            fields,
            [1, "[Not Set]"],
            [2, "[Empty]"],
            [0, "QWERTY"],
        ]

        export_as_csv(self.model_admin_mock, mock.Mock(), collection)
        self._assert_correct_csv(self.output_stream, expected_rows)

    def test_export_as_csv_no_header(self):
        """
        Test export_as_csv - no header.3
        """
        fields = ["code", "name"]
        collection = [
            DummyFactory(code=1, name="dummy 1"),
            DummyFactory(code=2, name="dummy 2"),
        ]

        export_as_csv = export_as_csv_action(fields=fields, header=False)

        expected_rows = [
            [1, "dummy 1"],
            [2, "dummy 2"],
        ]

        export_as_csv(self.model_admin_mock, mock.Mock(), collection)
        self._assert_correct_csv(self.output_stream, expected_rows)

    def test_export_as_csv_actual_model(self):
        """
        Tests export_as_csv as it is used in EnterpriseCustomer admin.
        """
        fields = EnterpriseCustomerAdmin.EXPORT_AS_CSV_FIELDS
        collection = [
            EnterpriseCustomerFactory(),
            EnterpriseCustomerFactory(),
            EnterpriseCustomerFactory(),
        ]

        for item in collection:
            EnterpriseCustomerIdentityProviderFactory(enterprise_customer=item)

        expected_rows = [fields] + [[getattr(customer, field) for field in fields] for customer in collection]

        export_as_csv = export_as_csv_action("CSV Export", fields=fields)
        export_as_csv(self.model_admin_mock, mock.Mock(), collection)
        self._assert_correct_csv(self.output_stream, expected_rows)
