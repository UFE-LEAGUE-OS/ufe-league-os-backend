#!/usr/bin/env python
"""
Standalone script to populate superadmin data.
Run with: python backend/scripts/populate_superadmin_data.py
"""

import os
import sys
import django
from datetime import timedelta
from django.utils import timezone
from django.core.management import call_command  # noqa: E402

# Setup Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.test_settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from accounts.models import User  # noqa: E402
from governance.models import (  # noqa: E402
    SportVariant,
    CompetitionFormat,
    Rule,
    LeagueStandard,
)
from rbac.models import (  # noqa: E402
    Permission,
    PermissionBundle,
    RoleTemplate,
    UserRoleAssignment,
)
from monitoring.models import (  # noqa: E402
    Anomaly,
    SecurityEvent,
    ComplianceTrail,
    TransactionReconciliation,
)
from dashboards.models import League  # noqa: E402


def create_super_admin():
    """Create or get super admin user."""
    # Use existing credentials
    super_admin, created = User.objects.get_or_create(
        email="admin@gmail.com",
        defaults={
            "first_name": "Admin",
            "last_name": "User",
            "role": User.Role.SUPER_ADMIN,
            "is_staff": True,
            "is_superuser": True,
            "is_email_verified": True,
            "is_phone_verified": True,
        },
    )
    if created:
        super_admin.set_password("Strong123!")
        super_admin.save()
        print(f"  + Created super admin: {super_admin.email}")
    else:
        print(f"  ✓ Super admin exists: {super_admin.email}")
        # Ensure password is correct if user already exists
        if not super_admin.has_usable_password():
            super_admin.set_password("Strong123!")
            super_admin.save()
            print(f"  ✓ Updated password for: {super_admin.email}")
    return super_admin


def clear_data():
    """Clear existing data."""
    print("  Clearing governance data...")
    LeagueStandard.objects.all().delete()
    Rule.objects.all().delete()
    CompetitionFormat.objects.all().delete()
    SportVariant.objects.all().delete()

    print("  Clearing RBAC data...")
    UserRoleAssignment.objects.all().delete()
    RoleTemplate.objects.all().delete()
    PermissionBundle.objects.all().delete()
    Permission.objects.all().delete()

    print("  Clearing monitoring data...")
    TransactionReconciliation.objects.all().delete()
    ComplianceTrail.objects.all().delete()
    SecurityEvent.objects.all().delete()
    Anomaly.objects.all().delete()


def populate_governance():
    """Populate governance module."""
    print("\n  Populating Governance module...")

    # Sport Variants
    print("    Creating sport variants...")
    sport_variants_data = [
        {
            "name": "Football 11-a-side",
            "slug": "football-11-a-side",
            "description": "Standard football format",
            "players_per_team": 11,
            "max_substitutes": 7,
            "match_duration_minutes": 90,
            "has_halftime": True,
            "halftime_duration_minutes": 15,
            "has_extra_time": True,
            "extra_time_duration_minutes": 30,
            "has_penalties": True,
            "max_red_cards_default": 1,
            "points_win": 3,
            "points_draw": 1,
            "points_loss": 0,
            "is_active": True,
            "is_verified": True,
        },
        {
            "name": "Futsal",
            "slug": "futsal",
            "description": "Indoor football format",
            "players_per_team": 5,
            "max_substitutes": 12,
            "match_duration_minutes": 40,
            "has_halftime": True,
            "halftime_duration_minutes": 15,
            "has_extra_time": False,
            "extra_time_duration_minutes": 0,
            "has_penalties": True,
            "max_red_cards_default": 2,
            "points_win": 3,
            "points_draw": 1,
            "points_loss": 0,
            "is_active": True,
            "is_verified": True,
        },
        {
            "name": "Beach Soccer",
            "slug": "beach-soccer",
            "description": "Football on sand",
            "players_per_team": 5,
            "max_substitutes": 5,
            "match_duration_minutes": 36,
            "has_halftime": True,
            "halftime_duration_minutes": 5,
            "has_extra_time": False,
            "has_penalties": True,
            "max_red_cards_default": 1,
            "points_win": 3,
            "points_draw": 1,
            "points_loss": 0,
            "is_active": True,
            "is_verified": True,
        },
    ]
    for variant_data in sport_variants_data:
        variant, created = SportVariant.objects.get_or_create(
            slug=variant_data["slug"], defaults=variant_data
        )
        if created:
            print(f"      + {variant.name}")

    # Competition Formats
    print("    Creating competition formats...")
    formats_data = [
        {
            "name": "Single Round Robin",
            "slug": "single-round-robin",
            "description": "Each team plays every other team once",
            "stage_type": CompetitionFormat.StageType.SINGLE_STAGE,
            "has_home_and_away": False,
            "max_teams_default": 20,
            "min_teams_default": 3,
            "tie_breakers": ["points", "goal_difference", "goals_scored"],
            "is_active": True,
            "is_verified": True,
        },
        {
            "name": "Double Round Robin",
            "slug": "double-round-robin",
            "description": "Each team plays every other team twice",
            "stage_type": CompetitionFormat.StageType.SINGLE_STAGE,
            "has_home_and_away": True,
            "max_teams_default": 20,
            "min_teams_default": 3,
            "tie_breakers": ["points", "goal_difference", "head_to_head"],
            "is_active": True,
            "is_verified": True,
        },
        {
            "name": "Group Stage + Knockout",
            "slug": "group-stage-knockout",
            "description": "Groups then knockout",
            "stage_type": CompetitionFormat.StageType.GROUP_KNOCKOUT,
            "has_home_and_away": False,
            "max_teams_default": 32,
            "min_teams_default": 8,
            "groups_count": 4,
            "teams_per_group": 4,
            "teams_qualify_per_group": 2,
            "has_third_place_match": True,
            "tie_breakers": ["points", "goal_difference"],
            "is_active": True,
            "is_verified": True,
        },
    ]
    for format_data in formats_data:
        fmt, created = CompetitionFormat.objects.get_or_create(
            slug=format_data["slug"], defaults=format_data
        )
        if created:
            print(f"      + {fmt.name}")

    # Rules
    print("    Creating rules...")
    rules_data = [
        {
            "title": "Licensing Requirements",
            "slug": "licensing-requirements",
            "rule_number": "FIN-001",
            "category": Rule.Category.COMPLIANCE,
            "priority": Rule.Priority.MANDATORY,
            "description": "All clubs must hold valid license",
            "summary": "Clubs must maintain valid annual licensing",
            "version": "1.0",
            "effective_date": timezone.now().date(),
            "is_active": True,
            "is_published": True,
            "published_at": timezone.now(),
        },
        {
            "title": "Squad Registration Rules",
            "slug": "squad-registration-rules",
            "rule_number": "COMP-001",
            "category": Rule.Category.COMPETITION,
            "priority": Rule.Priority.MANDATORY,
            "description": "Max 30-player squad, 18 per matchday",
            "summary": "Squad size limits",
            "version": "1.0",
            "effective_date": timezone.now().date(),
            "is_active": True,
            "is_published": True,
            "published_at": timezone.now(),
        },
        {
            "title": "Financial Fair Play",
            "slug": "ffp-guidelines",
            "rule_number": "FIN-002",
            "category": Rule.Category.FINANCIAL,
            "priority": Rule.Priority.MANDATORY,
            "description": "Losses limited to KES 50M over 3 years",
            "summary": "Financial fair play guidelines",
            "version": "1.0",
            "effective_date": timezone.now().date(),
            "is_active": True,
            "is_published": True,
            "published_at": timezone.now(),
        },
        {
            "title": "Disciplinary Code",
            "slug": "disciplinary-code",
            "rule_number": "DISC-001",
            "category": Rule.Category.DISCIPLINARY,
            "priority": Rule.Priority.MANDATORY,
            "description": "Yellow/red card sanctions",
            "summary": "Disciplinary procedures",
            "version": "1.0",
            "effective_date": timezone.now().date(),
            "is_active": True,
            "is_published": True,
            "published_at": timezone.now(),
        },
        {
            "title": "Stadium Safety Standards",
            "slug": "stadium-safety",
            "rule_number": "SAFE-001",
            "category": Rule.Category.SAFETY,
            "priority": Rule.Priority.MANDATORY,
            "description": "Minimum safety requirements",
            "summary": "Stadium safety standards",
            "version": "1.0",
            "effective_date": timezone.now().date(),
            "is_active": True,
            "is_published": True,
            "published_at": timezone.now(),
        },
    ]
    rules = []
    for rule_data in rules_data:
        rule, created = Rule.objects.get_or_create(
            slug=rule_data["slug"], version=rule_data["version"], defaults=rule_data
        )
        rules.append(rule)
        if created:
            print(f"      + {rule.title}")

    # League Standards
    print("    Publishing standards to leagues...")
    leagues = League.objects.filter(is_active=True)[:3]
    if leagues.exists():
        for league in leagues:
            for rule in rules[:3]:
                standard, created = LeagueStandard.objects.get_or_create(
                    rule=rule,
                    league=league,
                    defaults={
                        "assigned_by": None,
                        "notes": f"Standard rule for {league.name}",
                    },
                )
                if created:
                    print(f"      + {rule.title} → {league.name}")
    else:
        print("      ⚠ No leagues found, skipping league standards")


def populate_rbac():
    """Populate RBAC module."""
    print("\n    Populating RBAC module...")

    # Permissions
    print("      Creating permissions...")
    permissions_data = [
        {
            "codename": "dashboard.super_admin",
            "name": "Super Admin Dashboard",
            "category": "dashboard",
        },
        {
            "codename": "dashboard.league_admin",
            "name": "League Admin Dashboard",
            "category": "dashboard",
        },
        {
            "codename": "dashboard.club_admin",
            "name": "Club Admin Dashboard",
            "category": "dashboard",
        },
        {
            "codename": "governance.manage",
            "name": "Manage Governance",
            "category": "governance",
        },
        {
            "codename": "monitoring.view",
            "name": "View Monitoring",
            "category": "monitoring",
        },
        {"codename": "rbac.manage", "name": "Manage RBAC", "category": "rbac"},
        {
            "codename": "analytics.view",
            "name": "View Analytics",
            "category": "analytics",
        },
        {
            "codename": "sponsorships.manage",
            "name": "Manage Sponsorships",
            "category": "sponsorships",
        },
        {
            "codename": "ticketing.manage",
            "name": "Manage Ticketing",
            "category": "ticketing",
        },
        {
            "codename": "engagements.manage",
            "name": "Manage Engagements",
            "category": "engagements",
        },
    ]
    for perm_data in permissions_data:
        perm, created = Permission.objects.get_or_create(
            codename=perm_data["codename"], defaults=perm_data
        )
        if created:
            print(f"        + {perm.codename}")

    # Permission Bundles
    print("      Creating permission bundles...")
    bundles_data = [
        {
            "name": "Super Admin Bundle",
            "slug": "super-admin-bundle",
            "description": "Full system access",
            "permissions": list(Permission.objects.all()),
        },
        {
            "name": "League Admin Bundle",
            "slug": "league-admin-bundle",
            "description": "League management access",
            "permissions": list(
                Permission.objects.filter(
                    category__in=["dashboard", "governance", "analytics"]
                )
            ),
        },
    ]
    for bundle_data in bundles_data:
        bundle, created = PermissionBundle.objects.get_or_create(
            slug=bundle_data["slug"],
            defaults={
                "name": bundle_data["name"],
                "description": bundle_data["description"],
            },
        )
        if created:
            bundle.permissions.set(bundle_data["permissions"])
            print(f"        + {bundle.name}")

    # Role Templates
    print("      Creating role templates...")
    templates_data = [
        {
            "name": "Super Administrator",
            "slug": "super-administrator",
            "description": "Full system administrator",
            "bundles": list(PermissionBundle.objects.all()),
        },
        {
            "name": "League Administrator",
            "slug": "league-administrator",
            "description": "League-level administrator",
            "bundles": list(
                PermissionBundle.objects.filter(name="League Admin Bundle")
            ),
        },
    ]
    for template_data in templates_data:
        template, created = RoleTemplate.objects.get_or_create(
            slug=template_data["slug"],
            defaults={
                "name": template_data["name"],
                "description": template_data["description"],
            },
        )
        if created:
            template.bundles.set(template_data["bundles"])
            print(f"        + {template.name}")


def populate_monitoring(super_admin):
    """Populate monitoring module."""
    print("\n    Populating Monitoring module...")

    # Anomalies
    print("      Creating anomalies...")
    anomalies_data = [
        {
            "anomaly_type": Anomaly.AnomalyType.UNUSUAL_ACTIVITY,
            "severity": Anomaly.Severity.MEDIUM,
            "status": Anomaly.Status.OPEN,
            "description": "Multiple failed login attempts detected",
            "affected_user": super_admin,
        },
        {
            "anomaly_type": Anomaly.AnomalyType.PAYMENT_ANOMALY,
            "severity": Anomaly.Severity.HIGH,
            "status": Anomaly.Status.INVESTIGATING,
            "description": "Unusual payment pattern detected",
            "affected_user": super_admin,
        },
    ]
    for anomaly_data in anomalies_data:
        anomaly, created = Anomaly.objects.get_or_create(
            anomaly_type=anomaly_data["anomaly_type"],
            description=anomaly_data["description"],
            defaults=anomaly_data,
        )
        if created:
            print(f"        + {anomaly.anomaly_type}")

    # Security Events
    print("      Creating security events...")
    security_events_data = [
        {
            "event_type": SecurityEvent.EventType.UNAUTHORIZED_ACCESS,
            "severity": SecurityEvent.Severity.HIGH,
            "is_resolved": False,
            "description": "Unauthorized access attempt to admin panel",
        },
        {
            "event_type": SecurityEvent.EventType.SUSPICIOUS_LOGIN,
            "severity": SecurityEvent.Severity.MEDIUM,
            "is_resolved": True,
            "description": "Login from new device detected",
            "resolved_by": super_admin,
            "resolved_at": timezone.now() - timedelta(hours=2),
            "resolution_notes": "User confirmed it was them",
        },
    ]
    for event_data in security_events_data:
        event, created = SecurityEvent.objects.get_or_create(
            event_type=event_data["event_type"],
            description=event_data["description"],
            defaults=event_data,
        )
        if created:
            print(f"        + {event.event_type}")

    # Compliance Trails
    print("      Creating compliance trails...")
    compliance_data = [
        {
            "category": ComplianceTrail.Category.DATA_ACCESS,
            "action": "User data exported",
            "status": ComplianceTrail.Status.COMPLETED,
            "description": "Bulk user data export for audit",
        },
        {
            "category": ComplianceTrail.Category.PERMISSION_CHANGE,
            "action": "Role assignment updated",
            "status": ComplianceTrail.Status.COMPLETED,
            "description": "Updated league admin permissions",
        },
    ]
    for trail_data in compliance_data:
        trail, created = ComplianceTrail.objects.get_or_create(
            category=trail_data["category"],
            action=trail_data["action"],
            defaults=trail_data,
        )
        if created:
            print(f"        + {trail.category}")

    # Transaction Reconciliations
    print("      Creating transaction reconciliations...")
    reconciliations_data = [
        {
            "status": TransactionReconciliation.Status.VERIFIED,
            "is_verified": True,
            "verified_by": super_admin,
            "verified_at": timezone.now() - timedelta(days=1),
            "total_amount": 150000.00,
            "transaction_count": 45,
            "notes": "Monthly reconciliation complete",
        },
    ]
    for recon_data in reconciliations_data:
        recon, created = TransactionReconciliation.objects.get_or_create(
            total_amount=recon_data["total_amount"],
            defaults=recon_data,
        )
        if created:
            print(f"        + Reconciliation #{recon.id}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Populate superadmin test data")
    parser.add_argument(
        "--clear", action="store_true", help="Clear existing data first"
    )
    parser.add_argument(
        "--module", choices=["governance", "rbac", "monitoring", "all"], default="all"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("SUPERADMIN DATA SEEDING SCRIPT")
    print("=" * 70)

    # Run migrations
    print("\n[1/4] Running migrations...")
    call_command("migrate", verbosity=0)
    print("✓ Migrations complete")

    # Create super admin
    print("\n[2/4] Creating super admin user...")
    super_admin = create_super_admin()
    print(f"✓ Super admin ready: {super_admin.email}")

    # Clear if requested
    if args.clear:
        print("\n[3/4] Clearing existing data...")
        clear_data()
        print("✓ Data cleared")
    else:
        print("\n[3/4] Skipping clear (use --clear to clear data)")

    # Populate data
    print("\n[4/4] Populating data...")
    module = args.module

    if module in ["governance", "all"]:
        populate_governance()

    if module in ["rbac", "all"]:
        populate_rbac()

    if module in ["monitoring", "all"]:
        populate_monitoring(super_admin)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Sport Variants: {SportVariant.objects.count()}")
    print(f"  Competition Formats: {CompetitionFormat.objects.count()}")
    print(f"  Rules: {Rule.objects.count()}")
    print(f"  League Standards: {LeagueStandard.objects.count()}")
    print(f"  Permissions: {Permission.objects.count()}")
    print(f"  Permission Bundles: {PermissionBundle.objects.count()}")
    print(f"  Role Templates: {RoleTemplate.objects.count()}")
    print(f"  Anomalies: {Anomaly.objects.count()}")
    print(f"  Security Events: {SecurityEvent.objects.count()}")
    print(f"  Compliance Trails: {ComplianceTrail.objects.count()}")
    print(f"  Transaction Reconciliations: {TransactionReconciliation.objects.count()}")

    print("\n✓ Superadmin data populated successfully!")
    print("\nYou can now access superadmin pages with test data.")
    print(f"Super admin credentials: {super_admin.email} / SuperAdmin123!")


if __name__ == "__main__":
    main()
