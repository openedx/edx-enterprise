"""
Helpers that remove a learner's pending enterprise invites when the learner is retired.

Pending invites (``PendingEnterpriseCustomerUser`` and ``PendingEnterpriseCustomerAdminUser``) only hold an
email address, so they can only be matched on the learner's original email.

Every invite is removed in this order, so no copy of the email survives anywhere:

1. Overwrite ``user_email`` with a per-row placeholder. The data warehouse replicates deletes as soft deletes
   and keeps a row's last values, so the row is blanked before it is deleted. The placeholder is never the
   LMS retired email: ``handle_user_post_save`` links pending invites to any user whose email matches, so
   writing the retired email would link the invite to the retired account.
2. Delete the invite's pending group memberships, as ``remove_expired_pending_group_memberships`` does, after
   redacting their Django admin log entries (a membership's ``__str__`` includes its invite's, so the email).
   Deleting the invite alone would leave memberships with no member, which the group learners API cannot serialize.
3. Delete the invite.
4. Blank, then delete, every history row of the invite.
5. Redact the Django admin log entries for the invite. Their ``object_repr`` is the invite's ``__str__``, which
   includes the email. The entries are kept, without the email, as the record of the staff action.

The live row is blanked with ``QuerySet.update()`` so that no ``post_save`` receiver runs (saving a pending
admin invite creates a pending learner invite). Its history is removed in step 4 anyway.

History rows holding the email that belong to other invites (deleted earlier, or since changed to another email in
the admin) are blanked and deleted too. Only the rows holding the email are removed, so the history of an invite that
now belongs to someone else is kept. For such an invite, only the admin log entries that show the email are redacted.
"""
import logging

from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from enterprise.models import (
    EnterpriseGroupMembership,
    PendingEnterpriseCustomerAdminUser,
    PendingEnterpriseCustomerUser,
)

logger = logging.getLogger(__name__)

PENDING_INVITE_MODELS = (PendingEnterpriseCustomerAdminUser, PendingEnterpriseCustomerUser)


def _empty_counts():
    return {'invites': 0, 'group_memberships': 0, 'history_rows': 0, 'admin_log_entries': 0}


def redacted_invite_email(invite_id):
    """
    Return the placeholder email written to an invite and its history before they are deleted.
    """
    return f'retired-invite-{invite_id}@retired.invalid'


def redacted_admin_log_repr(model, object_id):
    """
    Return the text that replaces the email-bearing ``object_repr`` of an object's admin log entries.
    """
    return f'<{model._meta.object_name} {object_id}>: redacted on retirement'


def _redact_and_delete_history(model, invite_id, history_ids=None):
    """
    Blank and delete history rows of one invite: all of them, or only ``history_ids``. Returns the rows deleted.
    """
    rows = model.history.model.objects.filter(id=invite_id)
    if history_ids is not None:
        rows = rows.filter(history_id__in=history_ids)
    rows.update(user_email=redacted_invite_email(invite_id))
    return rows.delete()[0]


def _redact_admin_log(model, object_id, email=None):
    """
    Replace ``object_repr`` on the admin log entries of one object, or only on those that show ``email``.

    Returns the number of entries changed.
    """
    replacement = redacted_admin_log_repr(model, object_id)
    entries = LogEntry.objects.filter(content_type=ContentType.objects.get_for_model(model), object_id=str(object_id))
    if email is not None:
        entries = entries.filter(object_repr__icontains=email)
    return entries.exclude(object_repr=replacement).update(object_repr=replacement)


def _delete_pending_group_memberships(model, invite_id):
    """
    Redact the admin log entries of a pending learner invite's group memberships, then hard-delete them.

    Returns a ``(memberships_deleted, admin_log_entries_redacted)`` tuple.
    """
    if model is not PendingEnterpriseCustomerUser:
        return 0, 0
    memberships = EnterpriseGroupMembership.all_objects.filter(pending_enterprise_customer_user_id=invite_id)
    redacted = 0
    for membership in memberships:
        redacted += _redact_admin_log(EnterpriseGroupMembership, membership.uuid)
        membership.delete(soft=False)
    return len(memberships), redacted


def redact_and_delete_invites(model, invite_ids):
    """
    Remove the given live invites of ``model``, following the order in the module docstring.

    Arguments:
        model: ``PendingEnterpriseCustomerUser`` or ``PendingEnterpriseCustomerAdminUser``.
        invite_ids: ids of the invites. Ids that no longer exist are skipped.

    Returns:
        A dict with the number of invites, group memberships and history rows deleted, and of admin log entries
        redacted. It holds no personal data, so it can be logged.
    """
    counts = _empty_counts()
    with transaction.atomic():
        for invite_id in invite_ids:
            invite = model.objects.filter(id=invite_id)
            if not invite.update(user_email=redacted_invite_email(invite_id)):
                continue
            memberships_deleted, membership_log_redacted = _delete_pending_group_memberships(model, invite_id)
            counts['group_memberships'] += memberships_deleted
            counts['admin_log_entries'] += membership_log_redacted
            counts['invites'] += invite.delete()[1].get(model._meta.label, 0)
            counts['history_rows'] += _redact_and_delete_history(model, invite_id)
            counts['admin_log_entries'] += _redact_admin_log(model, invite_id)
    return counts


def _remove_email_from_other_invites_history(model, email, live_invite_ids):
    """
    Blank and delete the history rows holding ``email`` of invites other than ``live_invite_ids``.

    All admin log entries of an invite that no longer exists are redacted. An invite that still exists now
    belongs to another email, so only its entries that show ``email`` are. Returns a counts dict like
    ``redact_and_delete_invites``.
    """
    counts = _empty_counts()
    rows = model.history.model.objects.filter(user_email__iexact=email).exclude(id__in=live_invite_ids)
    history_ids_by_invite = {}
    for invite_id, history_id in rows.values_list('id', 'history_id'):
        history_ids_by_invite.setdefault(invite_id, []).append(history_id)
    with transaction.atomic():
        for invite_id, history_ids in history_ids_by_invite.items():
            counts['history_rows'] += _redact_and_delete_history(model, invite_id, history_ids)
            invite_exists = model.objects.filter(id=invite_id).exists()
            counts['admin_log_entries'] += _redact_admin_log(model, invite_id, email if invite_exists else None)
    return counts


def retire_pending_invites_for_email(original_email):
    """
    Remove every pending learner and admin invite for ``original_email`` with its group memberships and
    history, redact their admin log entries, and remove ``original_email`` from the history of other invites.

    Matching is case-insensitive. Safe to call more than once: a second call finds nothing.

    Returns:
        A dict of counts. It holds no personal data, so it can be logged.
    """
    totals = {'group_memberships': 0, 'history_rows': 0, 'admin_log_entries': 0}
    for model in PENDING_INVITE_MODELS:
        invite_ids = list(model.objects.filter(user_email__iexact=original_email).values_list('id', flat=True))
        counts = redact_and_delete_invites(model, invite_ids)
        history_counts = _remove_email_from_other_invites_history(model, original_email, invite_ids)
        totals[model._meta.model_name] = counts['invites']
        for key in ('group_memberships', 'history_rows', 'admin_log_entries'):
            totals[key] += counts[key] + history_counts[key]
    return totals
