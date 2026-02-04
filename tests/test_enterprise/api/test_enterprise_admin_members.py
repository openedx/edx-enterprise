"""Tests for enterprise admin members API viewset."""

from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework import response
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from enterprise.api.v1.views import enterprise_admin_members as members_view  # pylint: disable=no-name-in-module

@pytest.mark.django_db
def test_get_admin_members_returns_paginated_response(monkeypatch):
    user = get_user_model().objects.create_user(
        username="enterprise_admin", email="admin@example.com", password="test-pass"
    )
    factory = APIRequestFactory()
    django_request = factory.get("/", {"user_query": "search", "sort_by": "email", "is_reversed": True})
    django_request.user = user

    view = members_view.EnterpriseAdminMembersViewSet()
    drf_request = Request(django_request)

    serializer_instance = mock.Mock()
    serializer_instance.is_valid.return_value = None
    serializer_instance.validated_data = {"user_query": "search", "sort_by": "email", "is_reversed": True}
    serializer_cls = mock.Mock(return_value=serializer_instance)
    monkeypatch.setattr(
        members_view.serializers,
        "EnterpriseAdminMembersRequestQuerySerializer",
        serializer_cls,
    )

    union_qs = mock.Mock()
    ordered_qs = mock.Mock()
    union_qs.order_by.return_value = ordered_qs
    mock_get_union = mock.Mock(return_value=union_qs)
    monkeypatch.setattr(
        members_view.EnterpriseAdminMembersViewSet,
        "_get_union_queryset",
        mock_get_union,
    )

    mock_paginate = mock.Mock(return_value=["page"])
    monkeypatch.setattr(
        members_view.EnterpriseAdminMembersViewSet,
        "paginate_queryset",
        mock_paginate,
    )

    serializer_result = mock.Mock()
    serializer_result.data = [{"email": "user@example.com"}]
    mock_get_serializer = mock.Mock(return_value=serializer_result)
    monkeypatch.setattr(
        members_view.EnterpriseAdminMembersViewSet,
        "get_serializer",
        mock_get_serializer,
    )

    expected_response = response.Response({"status": "ok"})
    monkeypatch.setattr(
        members_view.EnterpriseAdminMembersPaginator,
        "get_paginated_response",
        lambda self, data: expected_response,
    )

    view_method = members_view.EnterpriseAdminMembersViewSet.get_admin_members.__wrapped__
    response_obj = view_method(view, drf_request, enterprise_uuid="enterprise-uuid")

    assert response_obj is expected_response
    serializer_cls.assert_called_once_with(data=drf_request.query_params)
    mock_get_union.assert_called_once_with("enterprise-uuid", "search")
    union_qs.order_by.assert_called_once_with("-email", "email")
    mock_paginate.assert_called_once_with(ordered_qs)
    mock_get_serializer.assert_called_once_with(["page"], many=True)


@pytest.mark.django_db
def test_get_admin_members_returns_validation_error(monkeypatch):
    user = get_user_model().objects.create_user(
        username="enterprise_admin2", email="admin2@example.com", password="test-pass"
    )
    factory = APIRequestFactory()
    django_request = factory.get("/", {"sort_by": "does_not_exist"})
    django_request.user = user

    view = members_view.EnterpriseAdminMembersViewSet()
    drf_request = Request(django_request)

    serializer_instance = mock.Mock()
    validation_detail = {"user_query": ["is required"]}
    serializer_instance.is_valid.side_effect = ValidationError(validation_detail)
    serializer_cls = mock.Mock(return_value=serializer_instance)
    monkeypatch.setattr(
        members_view.serializers,
        "EnterpriseAdminMembersRequestQuerySerializer",
        serializer_cls,
    )

    view_method = members_view.EnterpriseAdminMembersViewSet.get_admin_members.__wrapped__
    response_obj = view_method(view, drf_request, enterprise_uuid="enterprise-uuid")

    assert response_obj.status_code == 400
    assert response_obj.data == {"detail": validation_detail}
    serializer_instance.is_valid.assert_called_once_with(raise_exception=True)


@pytest.mark.django_db
def test_get_admin_members_applies_search_with_default_sort(monkeypatch):
    user = get_user_model().objects.create_user(
        username="enterprise_admin3", email="admin3@example.com", password="test-pass"
    )
    factory = APIRequestFactory()
    django_request = factory.get("/", {"user_query": "alice"})
    django_request.user = user

    view = members_view.EnterpriseAdminMembersViewSet()
    drf_request = Request(django_request)

    serializer_instance = mock.Mock()
    serializer_instance.is_valid.return_value = None
    serializer_instance.validated_data = {"user_query": "alice"}  # no sort_by/is_reversed
    serializer_cls = mock.Mock(return_value=serializer_instance)
    monkeypatch.setattr(
        members_view.serializers,
        "EnterpriseAdminMembersRequestQuerySerializer",
        serializer_cls,
    )

    union_qs = mock.Mock()
    ordered_qs = mock.Mock()
    union_qs.order_by.return_value = ordered_qs
    mock_get_union = mock.Mock(return_value=union_qs)
    monkeypatch.setattr(
        members_view.EnterpriseAdminMembersViewSet,
        "_get_union_queryset",
        mock_get_union,
    )

    mock_paginate = mock.Mock(return_value=["page"])
    monkeypatch.setattr(
        members_view.EnterpriseAdminMembersViewSet,
        "paginate_queryset",
        mock_paginate,
    )

    serializer_result = mock.Mock()
    serializer_result.data = [{"email": "alice@example.com"}]
    mock_get_serializer = mock.Mock(return_value=serializer_result)
    monkeypatch.setattr(
        members_view.EnterpriseAdminMembersViewSet,
        "get_serializer",
        mock_get_serializer,
    )

    expected_response = response.Response({"status": "ok"})
    monkeypatch.setattr(
        members_view.EnterpriseAdminMembersPaginator,
        "get_paginated_response",
        lambda self, data: expected_response,
    )

    view_method = members_view.EnterpriseAdminMembersViewSet.get_admin_members.__wrapped__
    response_obj = view_method(view, drf_request, enterprise_uuid="enterprise-uuid")

    assert response_obj is expected_response
    mock_get_union.assert_called_once_with("enterprise-uuid", "alice")
    union_qs.order_by.assert_called_once_with("name", "email")
    mock_paginate.assert_called_once_with(ordered_qs)
    mock_get_serializer.assert_called_once_with(["page"], many=True)
