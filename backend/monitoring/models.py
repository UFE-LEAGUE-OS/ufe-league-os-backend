from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Anomaly(models.Model):
    """Detected anomalies in platform activity."""

    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        INVESTIGATING = "INVESTIGATING", "Investigating"
        RESOLVED = "RESOLVED", "Resolved"
        FALSE_POSITIVE = "FALSE_POSITIVE", "False Positive"

    anomaly_type = models.CharField(max_length=100)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    title = models.CharField(max_length=300)
    description = models.TextField()
    detection_source = models.CharField(max_length=100)
    affected_user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="anomalies"
    )
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    assigned_to = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_anomalies",
    )
    resolved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_anomalies",
    )
    resolution_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
            models.Index(fields=["anomaly_type"]),
        ]

    def __str__(self):
        return f"{self.anomaly_type} - {self.severity} - {self.status}"


class PaymentAudit(models.Model):
    """Audit trail for payment-related activities across ticketing, membership, and sponsorship."""

    class PaymentSource(models.TextChoices):
        TICKETING = "TICKETING", "Ticketing"
        MEMBERSHIP = "MEMBERSHIP", "Membership"
        SPONSORSHIP = "SPONSORSHIP", "Sponsorship"
        WALLET = "WALLET", "Wallet"

    class EventType(models.TextChoices):
        INITIATED = "INITIATED", "Payment Initiated"
        COMPLETED = "COMPLETED", "Payment Completed"
        FAILED = "FAILED", "Payment Failed"
        REFUNDED = "REFUNDED", "Payment Refunded"
        CHARGEBACK = "CHARGEBACK", "Chargeback"
        DISPUTED = "DISPUTED", "Disputed"
        CANCELLED = "CANCELLED", "Payment Cancelled"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="payment_audits"
    )
    payment_source = models.CharField(max_length=20, choices=PaymentSource.choices)
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="UGX")
    reference = models.CharField(max_length=100)
    provider = models.CharField(max_length=50)
    provider_reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=50)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["payment_source", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["reference"]),
        ]

    def __str__(self):
        return f"{self.payment_source} {self.event_type} - {self.user.email} - {self.amount}"


class TransactionReconciliation(models.Model):
    """Transaction reconciliation records for accounting and audit purposes."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        MATCHED = "MATCHED", "Matched"
        UNMATCHED = "UNMATCHED", "Unmatched"
        DISCREPANCY = "DISCREPANCY", "Discrepancy"

    transaction_date = models.DateField()
    source_system = models.CharField(max_length=50)
    external_reference = models.CharField(max_length=100)
    internal_reference = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="UGX")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reconciliations",
    )
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        indexes = [
            models.Index(fields=["status", "-transaction_date"]),
            models.Index(fields=["source_system"]),
            models.Index(fields=["external_reference"]),
            models.Index(fields=["internal_reference"]),
        ]

    def __str__(self):
        return f"{self.source_system} - {self.external_reference} - {self.status}"


class SystemLog(models.Model):
    """System-level logs for monitoring platform health and errors."""

    class Level(models.TextChoices):
        DEBUG = "DEBUG", "Debug"
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"
        CRITICAL = "CRITICAL", "Critical"

    level = models.CharField(max_length=20, choices=Level.choices)
    logger_name = models.CharField(max_length=100)
    message = models.TextField()
    path = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    ip_address = models.CharField(max_length=45, blank=True)
    user_email = models.CharField(max_length=150, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["level", "-created_at"]),
            models.Index(fields=["logger_name"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.level} - {self.logger_name} - {self.message[:50]}"


class ComplianceTrail(models.Model):
    """Compliance and regulatory trail for governance purposes."""

    class Category(models.TextChoices):
        DATA_PROTECTION = "DATA_PROTECTION", "Data Protection"
        FINANCIAL = "FINANCIAL", "Financial Regulation"
        SPORTS_GOVERNANCE = "SPORTS_GOVERNANCE", "Sports Governance"
        ANTI_CORRUPTION = "ANTI_CORRUPTION", "Anti-Corruption"
        TAX = "TAX", "Tax Compliance"
        EMPLOYMENT = "EMPLOYMENT", "Employment Law"
        SAFETY = "SAFETY", "Safety & Security"

    category = models.CharField(max_length=30, choices=Category.choices)
    title = models.CharField(max_length=300)
    description = models.TextField()
    regulation_reference = models.CharField(max_length=100, blank=True)
    is_compliant = models.BooleanField(default=True)
    violation_details = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    assessed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="compliance_trails",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["is_compliant"]),
        ]

    def __str__(self):
        return f"{self.category} - {self.title}"


class DataAccessAudit(models.Model):
    """Audit trail for data access events."""

    class AccessType(models.TextChoices):
        READ = "READ", "Read"
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        DELETE = "DELETE", "Delete"
        EXPORT = "EXPORT", "Export"
        IMPORT = "IMPORT", "Import"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="data_access_audits"
    )
    access_type = models.CharField(max_length=20, choices=AccessType.choices)
    resource_type = models.CharField(max_length=100)
    resource_id = models.PositiveIntegerField(null=True, blank=True)
    resource_name = models.CharField(max_length=200, blank=True)
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    is_authorized = models.BooleanField(default=True)
    denial_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["resource_type", "-created_at"]),
            models.Index(fields=["is_authorized", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.access_type} - {self.resource_type}"


class SecurityEvent(models.Model):
    """Security events and alerts for monitoring."""

    class Severity(models.TextChoices):
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class EventType(models.TextChoices):
        LOGIN_SUCCESS = "LOGIN_SUCCESS", "Login Success"
        LOGIN_FAILURE = "LOGIN_FAILURE", "Login Failure"
        PASSWORD_CHANGE = "PASSWORD_CHANGE", "Password Change"
        PERMISSION_DENIED = "PERMISSION_DENIED", "Permission Denied"
        SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY", "Suspicious Activity"
        DATA_BREACH = "DATA_BREACH", "Data Breach"
        BRUTE_FORCE = "BRUTE_FORCE", "Brute Force Attempt"
        ACCOUNT_LOCKOUT = "ACCOUNT_LOCKOUT", "Account Lockout"

    event_type = models.CharField(max_length=30, choices=EventType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="security_events",
    )
    ip_address = models.CharField(max_length=45, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_security_events",
    )
    resolution_notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["severity", "-created_at"]),
            models.Index(fields=["is_resolved", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.severity} - {self.user.email if self.user else 'anonymous'}"
