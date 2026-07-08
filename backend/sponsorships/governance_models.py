"""
Sponsorship Governance Models
These models allow superadmins to configure and govern sponsorship operations.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class SponsorFramework(models.Model):
    """
    System-level sponsorship framework settings.
    Controls platform-wide sponsorship configuration.
    """

    class FrameworkType(models.TextChoices):
        PAYMENT_TIER = "PAYMENT_TIER", "Payment Tier Configuration"
        COMMISSION_STRUCTURE = "COMMISSION_STRUCTURE", "Commission Structure"
        APPROVAL_WORKFLOW = "APPROVAL_WORKFLOW", "Approval Workflow"
        VISIBILITY_SETTINGS = "VISIBILITY_SETTINGS", "Visibility Settings"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    framework_type = models.CharField(max_length=30, choices=FrameworkType.choices)
    configuration = models.JSONField(default=dict, help_text="Framework configuration")
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)
    effective_until = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_sponsor_frameworks",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_sponsor_frameworks",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["framework_type", "name"]
        indexes = [
            models.Index(fields=["framework_type", "is_active"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_framework_type_display()})"


class CampaignVisibilitySettings(models.Model):
    """
    Controls visibility and placement of sponsorship campaigns across the platform.
    """

    class VisibilityLevel(models.TextChoices):
        PUBLIC = "PUBLIC", "Public"
        RESTRICTED = "RESTRICTED", "Restricted"
        PRIVATE = "PRIVATE", "Private"
        PLATFORM_ONLY = "PLATFORM_ONLY", "Platform Only"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    visibility_level = models.CharField(max_length=30, choices=VisibilityLevel.choices)
    allowed_owner_types = models.JSONField(
        default=list, help_text="List of allowed owner types"
    )
    allowed_categories = models.JSONField(
        default=list, help_text="List of allowed sponsor categories"
    )
    max_active_campaigns = models.PositiveIntegerField(default=10)
    requires_approval = models.BooleanField(default=True)
    auto_publish = models.BooleanField(default=False)

    placement_rules = models.JSONField(
        default=dict, help_text="Placement positioning rules"
    )
    display_settings = models.JSONField(default=dict, help_text="Display configuration")

    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["visibility_level", "name"]
        indexes = [
            models.Index(fields=["visibility_level", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_visibility_level_display()}"


class SystemPlacement(models.Model):
    """
    System-level sponsorship placements across platform assets.
    """

    class PlacementType(models.TextChoices):
        HOMEPAGE_BANNER = "HOMEPAGE_BANNER", "Homepage Banner"
        HOMEPAGE_SIDEBAR = "HOMEPAGE_SIDEBAR", "Homepage Sidebar"
        LEAGUE_PAGE = "LEAGUE_PAGE", "League Page"
        CLUB_PAGE = "CLUB_PAGE", "Club Page"
        MATCH_PAGE = "MATCH_PAGE", "Match Page"
        FAN_DASHBOARD = "FAN_DASHBOARD", "Fan Dashboard"
        EMAIL_HEADER = "EMAIL_HEADER", "Email Header"
        PUSH_NOTIFICATION = "PUSH_NOTIFICATION", "Push Notification"
        IN_APP_BANNER = "IN_APP_BANNER", "In-App Banner"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    placement_type = models.CharField(max_length=30, choices=PlacementType.choices)
    max_slots = models.PositiveIntegerField(
        default=1, help_text="Maximum sponsors for this placement"
    )
    priority = models.PositiveIntegerField(
        default=0, help_text="Higher priority = more prominent"
    )

    dimensions = models.JSONField(
        default=dict, help_text="Placement dimensions and specifications"
    )
    pricing_rules = models.JSONField(
        default=dict, help_text="Pricing rules for this placement"
    )
    targeting_rules = models.JSONField(
        default=dict, help_text="Targeting and rotation rules"
    )

    is_active = models.BooleanField(default=True)
    is_exclusive = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "placement_type", "name"]
        indexes = [
            models.Index(fields=["placement_type", "is_active"]),
            models.Index(fields=["is_exclusive"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_placement_type_display()})"


class BenefitSharingPolicy(models.Model):
    """
    Platform-wide policies for benefit sharing and revenue distribution.
    """

    class PolicyType(models.TextChoices):
        REVENUE_SHARE = "REVENUE_SHARE", "Revenue Share Policy"
        BENEFIT_DISTRIBUTION = "BENEFIT_DISTRIBUTION", "Benefit Distribution Policy"
        PLATFORM_FEE = "PLATFORM_FEE", "Platform Fee Policy"
        PAYOUT_SCHEDULE = "PAYOUT_SCHEDULE", "Payout Schedule Policy"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    policy_type = models.CharField(max_length=30, choices=PolicyType.choices)
    rules = models.JSONField(default=dict, help_text="Policy rules and configurations")
    minimum_payout = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0"))],
    )
    payout_frequency = models.CharField(max_length=30, default="MONTHLY")

    applies_to = models.JSONField(
        default=dict, help_text="Which entities this policy applies to"
    )
    is_default = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(default=timezone.now)
    effective_until = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_benefit_policies",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_benefit_policies",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["policy_type", "name"]
        indexes = [
            models.Index(fields=["policy_type", "is_active"]),
            models.Index(fields=["is_default"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_policy_type_display()})"


class SponsorshipInventory(models.Model):
    """
    Tracks available sponsorship inventory across the platform.
    """

    class InventoryType(models.TextChoices):
        PACKAGE_SLOT = "PACKAGE_SLOT", "Package Slot"
        PLACEMENT_SLOT = "PLACEMENT_SLOT", "Placement Slot"
        BENEFIT_QUOTA = "BENEFIT_QUOTA", "Benefit Quota"
        CAMPAIGN_SLOT = "CAMPAIGN_SLOT", "Campaign Slot"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    inventory_type = models.CharField(max_length=30, choices=InventoryType.choices)
    total_quantity = models.PositiveIntegerField(default=0)
    allocated_quantity = models.PositiveIntegerField(default=0)
    available_quantity = models.PositiveIntegerField(default=0)

    belongs_to = models.ForeignKey(
        "sponsorships.SponsorPackage",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inventory_items",
    )
    placement = models.ForeignKey(
        SystemPlacement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="inventory_items",
    )

    allocation_rules = models.JSONField(
        default=dict, help_text="Rules for allocating this inventory"
    )
    expiry_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["inventory_type", "name"]
        indexes = [
            models.Index(fields=["inventory_type", "is_active"]),
        ]

    def __str__(self):
        return (
            f"{self.name} - {self.available_quantity}/{self.total_quantity} available"
        )

    def save(self, *args, **kwargs):
        self.available_quantity = max(0, self.total_quantity - self.allocated_quantity)
        super().save(*args, **kwargs)


class CampaignPerformance(models.Model):
    """
    Tracks performance metrics for sponsorship campaigns.
    """

    class MetricType(models.TextChoices):
        IMPRESSIONS = "IMPRESSIONS", "Impressions"
        CLICKS = "CLICKS", "Clicks"
        CONVERSIONS = "CONVERSIONS", "Conversions"
        ENGAGEMENT_RATE = "ENGAGEMENT_RATE", "Engagement Rate"
        ROI = "ROI", "Return on Investment"
        REACH = "REACH", "Reach"
        BRAND_AWARENESS = "BRAND_AWARENESS", "Brand Awareness"

    sponsor_package = models.ForeignKey(
        "sponsorships.SponsorPackage",
        on_delete=models.CASCADE,
        related_name="performance_metrics",
    )
    agreement = models.ForeignKey(
        "sponsorships.SponsorAgreement",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="performance_metrics",
    )

    metric_type = models.CharField(max_length=30, choices=MetricType.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()

    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="calculated_campaign_metrics",
    )
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end", "sponsor_package", "metric_type"]
        indexes = [
            models.Index(fields=["sponsor_package", "metric_type"]),
            models.Index(fields=["period_start", "period_end"]),
        ]

    def __str__(self):
        return f"{self.sponsor_package.name} - {self.get_metric_type_display()}: {self.value}"


class SponsorshipApprovalWorkflow(models.Model):
    """
    Configurable approval workflows for sponsorship packages and agreements.
    """

    class WorkflowType(models.TextChoices):
        PACKAGE_APPROVAL = "PACKAGE_APPROVAL", "Package Approval"
        AGREEMENT_APPROVAL = "AGREEMENT_APPROVAL", "Agreement Approval"
        PAYMENT_APPROVAL = "PAYMENT_APPROVAL", "Payment Approval"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    workflow_type = models.CharField(max_length=30, choices=WorkflowType.choices)
    steps = models.JSONField(default=list, help_text="Ordered list of approval steps")
    requires_finance_approval = models.BooleanField(default=False)
    requires_legal_approval = models.BooleanField(default=False)
    auto_approve_threshold = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Auto-approve if value below threshold",
    )

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["workflow_type", "name"]
        indexes = [
            models.Index(fields=["workflow_type", "is_active"]),
            models.Index(fields=["is_default"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_workflow_type_display()})"


class ComplianceAudit(models.Model):
    """
    Audit trail for sponsorship compliance checks.
    """

    class AuditType(models.TextChoices):
        KYC_VERIFICATION = "KYC_VERIFICATION", "KYC Verification"
        DOCUMENT_AUDIT = "DOCUMENT_AUDIT", "Document Audit"
        PAYMENT_AUDIT = "PAYMENT_AUDIT", "Payment Audit"
        BENEFIT_AUDIT = "BENEFIT_AUDIT", "Benefit Audit"
        CONTRACT_AUDIT = "CONTRACT_AUDIT", "Contract Audit"
        COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW", "Compliance Review"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        WAIVED = "WAIVED", "Waived"

    audit_type = models.CharField(max_length=30, choices=AuditType.choices)
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.PENDING
    )

    sponsor_account = models.ForeignKey(
        "sponsorships.SponsorAccount",
        on_delete=models.CASCADE,
        related_name="compliance_audits",
    )
    sponsor_package = models.ForeignKey(
        "sponsorships.SponsorPackage",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="compliance_audits",
    )
    agreement = models.ForeignKey(
        "sponsorships.SponsorAgreement",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="compliance_audits",
    )

    findings = models.JSONField(default=dict, help_text="Audit findings and issues")
    remediation_steps = models.JSONField(
        default=list, help_text="Required remediation steps"
    )
    auditor_notes = models.TextField(blank=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="performed_compliance_audits",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_compliance_audits",
    )

    performed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["audit_type", "status"]),
            models.Index(fields=["sponsor_account"]),
            models.Index(fields=["next_review_date"]),
        ]

    def __str__(self):
        return f"{self.get_audit_type_display()} - {self.sponsor_account.name} ({self.get_status_display()})"
