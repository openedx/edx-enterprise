# -*- coding: utf-8 -*-
"""
Custom `Django Admin actions`_ used in enterprise app.

.. _Django Admin actions: https://docs.djangoproject.com/en/1.8/ref/contrib/admin/actions/
"""

import unicodecsv
from six import string_types

from django.http import HttpResponse


def export_as_csv_action(description="Export selected objects as CSV file", fields=None, header=True):
    """
    Return an export csv action.

    Arguments:
        description (string): action description
        fields ([string]): list of model fields to include
        header (bool): whether or not to output the column names as the first row
    """
    # adapted from https://gist.github.com/mgerring/3645889
    def export_as_csv(modeladmin, request, queryset):  # pylint: disable=unused-argument
        """
        Export model fields to CSV.
        """
        opts = modeladmin.model._meta

        if not fields:
            field_names = [field.name for field in opts.fields]
        else:
            field_names = fields

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename={filename}.csv".format(
            filename=str(opts).replace(".", "_")
        )

        writer = unicodecsv.writer(response, encoding="utf-8")
        if header:
            writer.writerow(field_names)
        for obj in queryset:
            row = []
            for field_name in field_names:
                field = getattr(obj, field_name)
                if callable(field):
                    value = field()
                else:
                    value = field
                if value is None:
                    row.append("[Not Set]")
                elif not value and isinstance(value, string_types):
                    row.append("[Empty]")
                else:
                    row.append(value)
            writer.writerow(row)
        return response

    export_as_csv.short_description = description
    return export_as_csv
