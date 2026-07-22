from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.core.management import call_command
from governance.models import SportVariant, CompetitionFormat, Rule, LeagueStandard
from dashboards.models import League


class Command(BaseCommand):
    help = "Populates governance data with sample sport variants, competition formats, rules, and league standards"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing governance data before populating",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Running migrations...")
        call_command("migrate", verbosity=0)

        if options["clear"]:
            self.stdout.write("Clearing existing governance data...")
            LeagueStandard.objects.all().delete()
            Rule.objects.all().delete()
            CompetitionFormat.objects.all().delete()
            SportVariant.objects.all().delete()

        self.stdout.write("Populating governance data...")

        # ==================== SPORT VARIANTS ====================
        self.stdout.write("\nCreating sport variants...")
        sport_variants = self._create_sport_variants()
        self.stdout.write(f"✓ Created {len(sport_variants)} sport variants")

        # ==================== COMPETITION FORMATS ====================
        self.stdout.write("\nCreating competition formats...")
        competition_formats = self._create_competition_formats()
        self.stdout.write(f"✓ Created {len(competition_formats)} competition formats")

        # ==================== RULES & STANDARDS ====================
        self.stdout.write("\nCreating rules & standards...")
        rules = self._create_rules()
        self.stdout.write(f"✓ Created {len(rules)} rules & standards")

        # ==================== LEAGUE STANDARDS ====================
        self.stdout.write("\nPublishing standards to leagues...")
        league_standards = self._create_league_standards(rules)
        self.stdout.write(f"✓ Published {len(league_standards)} league standards")

        self.stdout.write(
            self.style.SUCCESS("\n✓ Governance data populated successfully!")
        )

    def _create_sport_variants(self):
        """Create sample sport variants."""
        variants_data = [
            {
                "name": "Football 11-a-side",
                "slug": "football-11-a-side",
                "description": "Standard football format with 11 players per team including goalkeeper.",
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
                "description": "Indoor football format played on a hard court with 5 players per team.",
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
                "description": "Football variant played on sand with 5 players per team.",
                "players_per_team": 5,
                "max_substitutes": 5,
                "match_duration_minutes": 36,
                "has_halftime": True,
                "halftime_duration_minutes": 5,
                "has_extra_time": False,
                "extra_time_duration_minutes": 0,
                "has_penalties": True,
                "max_red_cards_default": 1,
                "points_win": 3,
                "points_draw": 1,
                "points_loss": 0,
                "is_active": True,
                "is_verified": True,
            },
            {
                "name": "Football 7-a-side",
                "slug": "football-7-a-side",
                "description": "Small-sided football format with 7 players per team, commonly used for junior teams.",
                "players_per_team": 7,
                "max_substitutes": 5,
                "match_duration_minutes": 60,
                "has_halftime": True,
                "halftime_duration_minutes": 10,
                "has_extra_time": True,
                "extra_time_duration_minutes": 20,
                "has_penalties": True,
                "max_red_cards_default": 2,
                "points_win": 3,
                "points_draw": 1,
                "points_loss": 0,
                "is_active": True,
                "is_verified": True,
            },
            {
                "name": "Football 9-a-side",
                "slug": "football-9-a-side",
                "description": "Medium-sided football format with 9 players per team.",
                "players_per_team": 9,
                "max_substitutes": 5,
                "match_duration_minutes": 70,
                "has_halftime": True,
                "halftime_duration_minutes": 10,
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
        ]

        variants = []
        for variant_data in variants_data:
            variant, created = SportVariant.objects.get_or_create(
                slug=variant_data["slug"], defaults=variant_data
            )
            variants.append(variant)
            if created:
                self.stdout.write(f"  + Created: {variant.name}")
            else:
                self.stdout.write(f"  ✓ Skipped: {variant.name} (already exists)")

        return variants

    def _create_competition_formats(self):
        """Create sample competition formats."""
        formats_data = [
            {
                "name": "Single Round Robin",
                "slug": "single-round-robin",
                "description": "Each team plays every other team once. Simple and efficient format.",
                "stage_type": CompetitionFormat.StageType.SINGLE_STAGE,
                "has_home_and_away": False,
                "max_teams_default": 20,
                "min_teams_default": 3,
                "tie_breakers": [
                    "points",
                    "goal_difference",
                    "goals_scored",
                    "head_to_head",
                ],
                "is_active": True,
                "is_verified": True,
            },
            {
                "name": "Double Round Robin",
                "slug": "double-round-robin",
                "description": "Each team plays every other team twice (home and away). The most common league format.",
                "stage_type": CompetitionFormat.StageType.SINGLE_STAGE,
                "has_home_and_away": True,
                "max_teams_default": 20,
                "min_teams_default": 3,
                "tie_breakers": [
                    "points",
                    "goal_difference",
                    "goals_scored",
                    "head_to_head",
                    "fair_play",
                ],
                "is_active": True,
                "is_verified": True,
            },
            {
                "name": "Group Stage + Knockout",
                "slug": "group-stage-knockout",
                "description": "Teams divided into groups, top teams advance to knockout stage. Popular for tournaments.",
                "stage_type": CompetitionFormat.StageType.GROUP_KNOCKOUT,
                "has_home_and_away": False,
                "max_teams_default": 32,
                "min_teams_default": 8,
                "groups_count": 4,
                "teams_per_group": 4,
                "teams_qualify_per_group": 2,
                "has_third_place_match": True,
                "tie_breakers": [
                    "points",
                    "goal_difference",
                    "goals_scored",
                    "head_to_head",
                ],
                "is_active": True,
                "is_verified": True,
            },
            {
                "name": "Single Elimination Knockout",
                "slug": "single-elimination-knockout",
                "description": "Straight knockout tournament where losers are eliminated after each round.",
                "stage_type": CompetitionFormat.StageType.SINGLE_STAGE,
                "has_home_and_away": False,
                "max_teams_default": 64,
                "min_teams_default": 4,
                "has_third_place_match": True,
                "tie_breakers": ["head_to_head", "penalty_shootout"],
                "is_active": True,
                "is_verified": True,
            },
            {
                "name": "Swiss System",
                "slug": "swiss-system",
                "description": "Non-elimination tournament where teams play opponents with similar records each round.",
                "stage_type": CompetitionFormat.StageType.SWISS,
                "has_home_and_away": False,
                "max_teams_default": 64,
                "min_teams_default": 8,
                "tie_breakers": ["points", "buchholz_score", "head_to_head"],
                "is_active": True,
                "is_verified": True,
            },
            {
                "name": "Double Elimination",
                "slug": "double-elimination",
                "description": "Teams are eliminated after losing two matches. Used in e-sports and some cup competitions.",
                "stage_type": CompetitionFormat.StageType.CUSTOM,
                "has_home_and_away": False,
                "max_teams_default": 16,
                "min_teams_default": 4,
                "has_third_place_match": False,
                "tie_breakers": ["head_to_head", "buildup_points"],
                "is_active": True,
                "is_verified": True,
            },
        ]

        formats = []
        for format_data in formats_data:
            fmt, created = CompetitionFormat.objects.get_or_create(
                slug=format_data["slug"], defaults=format_data
            )
            formats.append(fmt)
            if created:
                self.stdout.write(f"  + Created: {fmt.name}")
            else:
                self.stdout.write(f"  ✓ Skipped: {fmt.name} (already exists)")

        return formats

    def _create_rules(self):
        """Create sample rules and standards."""
        rules_data = [
            # Compliance & Legal
            {
                "title": "Licensing Requirements",
                "slug": "licensing-requirements",
                "rule_number": "FIN-001",
                "category": Rule.Category.COMPLIANCE,
                "priority": Rule.Priority.MANDATORY,
                "description": "All participating clubs must hold a valid club license issued by the federation. The license must be renewed annually and cover all competitions entered.",
                "summary": "Clubs must maintain valid annual licensing",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Clubs without valid license will be refused entry to competitions. Penalties include fines and point deductions.",
                "is_active": True,
                "is_published": True,
                "published_at": timezone.now(),
            },
            # Competition Rules
            {
                "title": "Squad Registration Rules",
                "slug": "squad-registration-rules",
                "rule_number": "COMP-001",
                "category": Rule.Category.COMPETITION,
                "priority": Rule.Priority.MANDATORY,
                "description": "Each club must register a maximum squad of 30 players for the league season. A matchday squad of 18 players must be submitted 48 hours before kickoff.",
                "summary": "Max 30-player squad, 18 players per matchday",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Failure to submit matchday squad on time may result in forfeiture of the match.",
                "is_active": True,
                "is_published": True,
                "published_at": timezone.now(),
            },
            {
                "title": "Player Eligibility and Transfer Regulations",
                "slug": "player-eligibility-regulations",
                "rule_number": "COMP-002",
                "category": Rule.Category.COMPETITION,
                "priority": Rule.Priority.MANDATORY,
                "description": "Players must be registered with their club and have valid insurance. Transfer windows are strictly enforced: January and July-August.",
                "summary": "Transfer windows strictly enforced",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Fielding ineligible players results in forfeiture of the match and potential fines.",
                "is_active": True,
                "is_published": True,
                "published_at": timezone.now(),
            },
            # Financial Regulations
            {
                "title": "Financial Fair Play Guidelines",
                "slug": "ffp-guidelines",
                "rule_number": "FIN-002",
                "category": Rule.Category.FINANCIAL,
                "priority": Rule.Priority.MANDATORY,
                "description": "Clubs must not exceed operational losses of KES 50 million over a rolling three-year period. Financial statements must be audited annually.",
                "summary": "Losses limited to KES 50M over 3 years",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Non-compliance may result in fines, transfer bans, or exclusion from competitions.",
                "is_active": True,
                "is_published": True,
                "published_at": timezone.now(),
            },
            # Disciplinary
            {
                "title": "Disciplinary Code",
                "slug": "disciplinary-code",
                "rule_number": "DISC-001",
                "category": Rule.Category.DISCIPLINARY,
                "priority": Rule.Priority.MANDATORY,
                "description": "Standard disciplinary procedures including yellow/red card sanctions, suspension thresholds, and appeal processes.",
                "summary": "Yellow/red card sanctions and appeals",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Yellow cards: 5 = 1-match ban. Red cards: automatic 3-match ban. Appeals to Disciplinary Committee within 7 days.",
                "is_active": True,
                "is_published": True,
                "published_at": timezone.now(),
            },
            # Safety & Security
            {
                "title": "Stadium Safety and Security Standards",
                "slug": "stadium-safety-standards",
                "rule_number": "SAFE-001",
                "category": Rule.Category.SAFETY,
                "priority": Rule.Priority.MANDATORY,
                "description": "All stadiums must meet minimum safety requirements including emergency exits, medical facilities, crowd control barriers, and fire safety systems.",
                "summary": "Stadiums must meet minimum safety requirements",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Inspection required before each season. Non-compliant stadiums may be banned from hosting matches.",
                "is_active": True,
                "is_published": True,
                "published_at": timezone.now(),
            },
            # Player Eligibility
            {
                "title": "Youth Player Protection Policy",
                "slug": "youth-player-protection",
                "rule_number": "PLAY-001",
                "category": Rule.Category.PLAYER_ELIGIBILITY,
                "priority": Rule.Priority.MANDATORY,
                "description": "Players under 18 must have parental consent, limited training hours, and educational support. Transfer restrictions for minors apply.",
                "summary": "Protection measures for under-18 players",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Clubs found violating may face transfer bans and fines.",
                "is_active": True,
                "is_published": True,
                "published_at": timezone.now(),
            },
            # Technical Standards
            {
                "title": "VAR Protocol Implementation",
                "slug": "var-protocol",
                "rule_number": "TECH-001",
                "category": Rule.Category.TECHNICAL,
                "priority": Rule.Priority.MANDATORY,
                "description": "Video Assistant Referee (VAR) must be used in all top-tier league matches. Minimum equipment requirements and training standards apply.",
                "summary": "VAR required for top-tier matches",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Technical assessment required before implementation. Ongoing calibration checks mandatory.",
                "is_active": True,
                "is_published": True,
                "published_at": timezone.now(),
            },
            {
                "title": "Match Ball Specifications",
                "slug": "match-ball-specifications",
                "rule_number": "TECH-002",
                "category": Rule.Category.TECHNICAL,
                "priority": Rule.Priority.ADVISORY,
                "description": "Match balls must meet FIFA Quality Pro or Quality standards. Size and weight specifications for each age category defined.",
                "summary": "FIFA quality standards for match balls",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Pre-match inspection by referee. Non-compliant balls may be rejected.",
                "is_active": True,
                "is_published": False,
            },
            # Registration & Transfers
            {
                "title": "Player Registration Procedures",
                "slug": "player-registration-procedures",
                "rule_number": "REG-001",
                "category": Rule.Category.REGISTRATION,
                "priority": Rule.Priority.MANDATORY,
                "description": "All player registrations must be submitted through the official online system. Supporting documents required including passport, medical certificate, and transfer certificate.",
                "summary": "Online registration system mandatory",
                "version": "1.0",
                "effective_date": timezone.now().date(),
                "enforcement_notes": "Incomplete registrations will be rejected. 48-hour processing time applies.",
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
                self.stdout.write(f"  + Created: {rule}")
            else:
                self.stdout.write(f"  ✓ Skipped: {rule} (already exists)")

        return rules

    def _create_league_standards(self, rules):
        """Publish selected rules to existing leagues."""
        if not League.objects.exists():
            self.stdout.write(
                "  ⚠ No leagues found. Skipping league standards creation."
            )
            return []

        leagues = League.objects.filter(is_active=True)
        if not leagues.exists():
            self.stdout.write(
                "  ⚠ No active leagues found. Skipping league standards creation."
            )
            return []

        # Define which rules should be published to which leagues
        league_rules_mapping = {}
        for league in leagues:
            # By default, publish all mandatory rules to all leagues
            mandatory_rules = [
                r for r in rules if r.priority == Rule.Priority.MANDATORY
            ]
            league_rules_mapping[league] = mandatory_rules

        standards = []
        for league, league_rules in league_rules_mapping.items():
            for rule in league_rules:
                standard, created = LeagueStandard.objects.get_or_create(
                    rule=rule,
                    league=league,
                    defaults={
                        "assigned_by": None,  # Super admin (no user in sample data)
                        "notes": f"Standard rule assigned to {league.name}",
                    },
                )
                standards.append(standard)
                if created:
                    status = "Published" if rule.is_published else "Assigned"
                    self.stdout.write(f"  + {status}: {rule.title} → {league.name}")
                else:
                    self.stdout.write(
                        f"  ✓ Skipped: {rule.title} → {league.name} (already exists)"
                    )

        return standards
