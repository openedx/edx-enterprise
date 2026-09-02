"""
Custom `Django Admin actions`_ used in enterprise app.

.. _Django Admin actions: https://docs.djangoproject.com/en/1.8/ref/contrib/admin/actions/
"""

import unicodecsv

from django.contrib import messages
from django.http import HttpResponse
from django.utils.safestring import mark_safe

from enterprise.api_client.enterprise_catalog import EnterpriseCatalogApiClient


def export_as_csv_action(description="Export selected objects as CSV file", fields=None, header=True):
    """
    Return an export csv action.

    Arguments:
        description (string): action description
        fields ([string]): list of model fields to include
        header (bool): whether or not to output the column names as the first row
    """
    # adapted from https://gist.github.com/mgerring/3645889
    def export_as_csv(modeladmin, request, queryset):
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
                elif not value and isinstance(value, str):
                    row.append("[Empty]")
                else:
                    row.append(value)
            writer.writerow(row)
        return response

    export_as_csv.short_description = description
    return export_as_csv


def refresh_catalog(self, request, queryset):
    """
    Kicks off background running tasks for refreshing catalogs
    """
    catalog_client = EnterpriseCatalogApiClient(user=request.user)
    refreshed_catalogs, failed_to_refresh_catalogs = catalog_client.refresh_catalogs(queryset)

    # display catalog and task ids that were successfully started refreshing
    updated_message = ''
    if refreshed_catalogs:
        updated_message = '<b>The following catalogs are being refreshed:</b><ul>'
        for uuid, task_id in refreshed_catalogs.items():
            updated_message = updated_message + '<li>' + str(uuid) + ' with task id: ' + str(task_id) + '</li>'
        updated_message = updated_message + '</ul>'

    # display catalog ids that failed to start refreshing
    if failed_to_refresh_catalogs:
        updated_message = updated_message + '<b>Failed to refresh catalogs with the following ids:</b><ul>'
        for failed_catalog_uuid in failed_to_refresh_catalogs:
            updated_message = updated_message + '<li class="error">' + str(failed_catalog_uuid) + '</li>'
        updated_message = updated_message + '</ul>'

    # Info level based on how successful refreshing catalogs was overall
    level = messages.INFO
    if failed_to_refresh_catalogs:
        level = messages.ERROR
        if refreshed_catalogs:
            level = messages.WARNING
    self.message_user(request, mark_safe(updated_message), level=level)
