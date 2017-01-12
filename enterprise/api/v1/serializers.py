"""
Serializers for enterprise api version 1.
"""
from __future__ import absolute_import, unicode_literals

from rest_framework import serializers

from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from enterprise import models


class SiteSerializer(serializers.ModelSerializer):
    """
    Serializer for Site model.
    """
    class Meta:
        model = Site
        fields = (
            'domain', 'name',
        )


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    """
    class Meta:
        model = User
        fields = (
            'username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'date_joined'
        )


class EnterpriseCustomerBrandingConfigurationSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerBrandingConfiguration model.
    """
    class Meta:
        model = models.EnterpriseCustomerBrandingConfiguration
        fields = (
            'enterprise_customer', 'logo'
        )


class EnterpriseCustomerEntitlementSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerEntitlement model.
    """
    class Meta:
        model = models.EnterpriseCustomerEntitlement
        fields = (
            'enterprise_customer', 'entitlement_id'
        )


class EnterpriseCustomerSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomer model.
    """
    class Meta:
        model = models.EnterpriseCustomer
        fields = (
            'uuid', 'name', 'catalog', 'active', 'site', 'enable_data_sharing_consent', 'enforce_data_sharing_consent',
            'enterprise_customer_users', 'branding_configuration', 'enterprise_customer_entitlements'
        )

    site = SiteSerializer()
    branding_configuration = EnterpriseCustomerBrandingConfigurationSerializer()
    enterprise_customer_entitlements = EnterpriseCustomerEntitlementSerializer(  # pylint: disable=invalid-name
        many=True,
    )


class UserDataSharingConsentAuditSerializer(serializers.ModelSerializer):
    """
    Serializer for UserDataSharingConsentAudit model.
    """
    class Meta:
        model = models.UserDataSharingConsentAudit
        fields = (
            'user', 'state', 'enabled'
        )


class EnterpriseCustomerUserSerializer(serializers.ModelSerializer):
    """
    Serializer for EnterpriseCustomerUser model.
    """
    class Meta:
        model = models.EnterpriseCustomerUser
        fields = (
            'enterprise_customer', 'user_id', 'user', 'data_sharing_consent'
        )

    user = UserSerializer()
    enterprise_customer = EnterpriseCustomerSerializer()
    data_sharing_consent = UserDataSharingConsentAuditSerializer(many=True)
