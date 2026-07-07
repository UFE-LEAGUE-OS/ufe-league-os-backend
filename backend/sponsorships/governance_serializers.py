"""
Sponsorship Governance Serializers
"""

from decimal import Decimal

from rest_framework import serializers

from .governance_models import (
    SponsorFramework,
    CampaignVisibilitySettings,
    SystemPlacement,
    BenefitSharingPolicy,
    SponsorshipInventory,
    CampaignPerformance,
    SponsorshipApprovalWorkflow,
    ComplianceAudit,
)


class SponsorFrameworkSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    updated_by_email = serializers.EmailField(source="updated_by.email", read_only=True)

    class Meta:
        model = SponsorFramework
        fields = [
            "id",
            "name",
            "slug",
            "framework_type",
            "configuration",
            "is_active",
            "effective_from",
            "effective_until",
            "created_by",
            "created_by_email",
            "updated_by",
            "updated_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CampaignVisibilitySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignVisibilitySettings
        fields = [
            "id",
            "name",
            "slug",
            "visibility_level",
            "allowed_owner_types",
            "allowed_categories",
            "max_active_campaigns",
            "requires_approval",
            "auto_publish",
            "placement_rules",
            "display_settings",
            "is_active",
            "effective_from",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SystemPlacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemPlacement
        fields = [
            "id",
            "name",
            "slug",
            "placement_type",
            "max_slots",
            "priority",
            "dimensions",
            "pricing_rules",
            "targeting_rules",
            "is_active",
            "is_exclusive",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class BenefitSharingPolicySerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    approved_by_email = serializers.EmailField(
        source="approved_by.email", read_only=True
    )

    class Meta:
        model = BenefitSharingPolicy
        fields = [
            "id",
            "name",
            "slug",
            "policy_type",
            "rules",
            "minimum_payout",
            "payout_frequency",
            "applies_to",
            "is_default",
            "is_active",
            "effective_from",
            "effective_until",
            "created_by",
            "created_by_email",
            "approved_by",
            "approved_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SponsorshipInventorySerializer(serializers.ModelSerializer):
    sponsor_package_name = serializers.CharField(
        source="belongs_to.name", read_only=True
    )
    placement_name = serializers.CharField(source="placement.name", read_only=True)

    class Meta:
        model = SponsorshipInventory
        fields = [
            "id",
            "name",
            "slug",
            "inventory_type",
            "total_quantity",
            "allocated_quantity",
            "available_quantity",
            "belongs_to",
            "sponsor_package_name",
            "placement",
            "placement_name",
            "allocation_rules",
            "expiry_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class CampaignPerformanceSerializer(serializers.ModelSerializer):
    sponsor_package_name = serializers.CharField(
        source="sponsor_package.name", read_only=True
    )
    calculated_by_email = serializers.EmailField(
        source="calculated_by.email", read_only=True
    )

    class Meta:
        model = CampaignPerformance
        fields = [
            "id",
            "sponsor_package",
            "sponsor_package_name",
            "agreement",
            "metric_type",
            "value",
            "period_start",
            "period_end",
            "calculated_by",
            "calculated_by_email",
            "is_verified",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SponsorshipApprovalWorkflowSerializer(serializers.ModelSerializer):
    class Meta:
        model = SponsorshipApprovalWorkflow
        fields = [
            "id",
            "name",
            "slug",
            "workflow_type",
            "steps",
            "requires_finance_approval",
            "requires_legal_approval",
            "auto_approve_threshold",
            "is_active",
            "is_default",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ComplianceAuditSerializer(serializers.ModelSerializer):
    sponsor_account_name = serializers.CharField(
        source="sponsor_account.name", read_only=True
    )
    sponsor_package_name = serializers.CharField(
        source="sponsor_package.name", read_only=True
    )
    performed_by_email = serializers.EmailField(
        source="performed_by.email", read_only=True
    )
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True
    )

    class Meta:
        model = ComplianceAudit
        fields = [
            "id",
            "audit_type",
            "status",
            "sponsor_account",
            "sponsor_account_name",
            "sponsor_package",
            "sponsor_package_name",
            "agreement",
            "findings",
            "remediation_steps",
            "auditor_notes",
            "performed_by",
            "performed_by_email",
            "reviewed_by",
            "reviewed_by_email",
            "performed_at",
            "completed_at",
            "next_review_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
