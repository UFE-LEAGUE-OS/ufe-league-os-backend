from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Club
from dashboards.models import (
    ClubAffiliation,
    Competition,
    CompetitionEdition,
    CompetitionIdentity,
    FixtureOfficialAssignment,
    League,
    Match,
    NationalTeam,
    NationalTeamMember,
    Season,
    UnionApproval,
    UnionAuditEvent,
    UnionDocumentReference,
    UnionMatchOfficial,
    UnionPlayer,
    UnionPlayerCompetitionEligibility,
    UnionPlayerRegistration,
    UnionPlayerTransfer,
    UnionRegistrationApplication,
    UnionReviewComment,
    UnionWorkspace,
)

DEMO_KEY = "league_os_union_workflow_coverage_v1"


class Command(BaseCommand):
    help = "Seed deterministic Union workflow records for API and UI coverage."

    @transaction.atomic
    def handle(self, *args, **options):
        contexts = [self._context(workspace) for workspace in self._workspaces()]

        for context in contexts:
            self._baseline(context)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded baseline workflow data for {context['workspace'].acronym}."
                )
            )

        coverage = next(
            (item for item in contexts if item["workspace"].acronym.upper() == "URU"),
            contexts[0],
        )
        self._full_coverage(coverage)
        self.stdout.write(self.style.SUCCESS("Union workflow coverage seed complete."))

    def _workspaces(self):
        workspaces = list(
            UnionWorkspace.objects.select_related("related_union")
            .filter(related_union__isnull=False)
            .order_by("id")
        )
        if not workspaces:
            raise CommandError(
                "Run the Union workspace and operations seed commands first."
            )
        return workspaces

    def _context(self, workspace):
        membership = (
            workspace.memberships.select_related("user")
            .filter(is_active=True, user__is_active=True)
            .order_by("id")
            .first()
        )
        league = League.objects.filter(
            union=workspace.related_union,
            is_active=True,
        ).first()
        competition = Competition.objects.filter(
            league__union=workspace.related_union,
            is_active=True,
        ).first()
        clubs = list(
            Club.objects.filter(
                league_memberships__league__union=workspace.related_union,
            )
            .distinct()
            .order_by("id")
        )
        match = Match.objects.filter(
            competition__league__union=workspace.related_union,
        ).first()

        if (
            not membership
            or not league
            or not competition
            or len(clubs) < 2
            or not match
        ):
            raise CommandError(
                f"{workspace.acronym} is missing users, clubs, competitions, or fixtures."
            )

        season, _ = Season.objects.update_or_create(
            league=league,
            slug=f"{workspace.slug}-coverage-2026",
            defaults={
                "name": f"{workspace.acronym} Coverage 2026",
                "start_date": date(2026, 1, 1),
                "end_date": date(2026, 12, 31),
                "is_active": True,
            },
        )
        if competition.season_record_id is None:
            competition.season_record = season
            competition.save(update_fields=["season_record", "updated_at"])

        edition = CompetitionEdition.objects.filter(competition=competition).first()
        if edition is None:
            identity = CompetitionIdentity.objects.filter(
                union=workspace.related_union,
                primary_league=league,
            ).first()
            if identity is None:
                identity, _ = CompetitionIdentity.objects.update_or_create(
                    union=workspace.related_union,
                    slug=f"{workspace.slug}-coverage",
                    defaults={
                        "primary_league": league,
                        "name": f"{workspace.acronym} Coverage Competition",
                        "sport": workspace.sport,
                        "competition_type": CompetitionIdentity.CompetitionType.LEAGUE,
                        "description": DEMO_KEY,
                        "is_active": True,
                    },
                )
            edition = CompetitionEdition.objects.create(
                identity=identity,
                competition=competition,
                season=season,
                status=CompetitionEdition.Status.ACTIVE,
                rules={"demo_key": DEMO_KEY},
                eligibility_rules={"demo_key": DEMO_KEY},
                published_at=timezone.now(),
                published_by=membership.user,
            )
        elif edition.season_id is None:
            edition.season = season
            edition.save(update_fields=["season", "updated_at"])

        return {
            "workspace": workspace,
            "actor": membership.user,
            "clubs": clubs,
            "competition": competition,
            "identity": edition.identity,
            "edition": edition,
            "season": edition.season or season,
            "match": match,
        }

    def _baseline(self, context):
        workspace = context["workspace"]
        actor = context["actor"]
        clubs = context["clubs"]
        player = self._player(context, "BASE", 1, UnionPlayer.Status.APPROVED)
        registration = self._registration(
            context,
            player,
            clubs[0],
            "BASE",
            UnionPlayerRegistration.Status.ACTIVE,
        )
        self._eligibility(
            context,
            player,
            registration,
            clubs[0],
            UnionPlayerCompetitionEligibility.Status.ELIGIBLE,
        )
        ClubAffiliation.objects.update_or_create(
            workspace=workspace,
            club=clubs[0],
            defaults={
                "status": ClubAffiliation.Status.ACTIVE,
                "expires_on": date(2027, 12, 31),
                "compliance_status": "COMPLIANT",
                "compliance_notes": DEMO_KEY,
                "liaison": actor,
            },
        )
        team, _ = NationalTeam.objects.update_or_create(
            workspace=workspace,
            slug=f"{workspace.slug}-coverage-senior",
            defaults={
                "name": f"{workspace.acronym} Coverage Senior Team",
                "category": "Senior",
                "status": NationalTeam.Status.ACTIVE,
                "notes": DEMO_KEY,
                "created_by": actor,
            },
        )
        NationalTeamMember.objects.update_or_create(
            team=team,
            full_name=player.full_name,
            member_type=NationalTeamMember.MemberType.PLAYER,
            defaults={
                "player": player,
                "club": clubs[0],
                "role": "Player",
                "status": NationalTeamMember.Status.ACTIVE,
                "notes": DEMO_KEY,
            },
        )
        application = self._application(
            context,
            1,
            UnionRegistrationApplication.Status.PENDING,
        )
        self._approval(
            context,
            application.id,
            "REVIEW_REGISTRATION",
            UnionApproval.Status.PENDING,
        )
        self._comment(context, "registration_application", application.id, "baseline")
        self._document(context, "union_player", player.id, "identity")
        self._audit(context, "coverage.baseline.created", player.id)
        official = self._official(
            context, "baseline", UnionMatchOfficial.RoleType.CENTRE_REFEREE
        )
        FixtureOfficialAssignment.objects.update_or_create(
            match=context["match"],
            official=official,
            role_type=official.role_type,
            defaults={
                "status": FixtureOfficialAssignment.Status.ASSIGNED,
                "notes": DEMO_KEY,
                "assigned_by": actor,
            },
        )

    def _full_coverage(self, context):
        self._player_states(context)
        self._registration_states(context)
        self._eligibility_states(context)
        self._transfer_states(context)
        self._affiliation_states(context)
        self._application_states(context)
        self._approval_states(context)
        self._team_states(context)
        self._assignment_states(context)
        self._governance_records(context)

    def _player_states(self, context):
        for index, status in enumerate(UnionPlayer.Status.values, 1):
            self._player(context, "PLAYER", index, status)

    def _registration_states(self, context):
        for index, status in enumerate(UnionPlayerRegistration.Status.values, 1):
            player = self._player(context, "REG", index, UnionPlayer.Status.APPROVED)
            self._registration(
                context,
                player,
                context["clubs"][index % len(context["clubs"])],
                f"REG_{status}",
                status,
            )

    def _eligibility_states(self, context):
        for index, status in enumerate(
            UnionPlayerCompetitionEligibility.Status.values,
            1,
        ):
            club = context["clubs"][index % len(context["clubs"])]
            player = self._player(context, "ELIG", index, UnionPlayer.Status.APPROVED)
            registration = self._registration(
                context,
                player,
                club,
                f"ELIG_{status}",
                UnionPlayerRegistration.Status.ACTIVE,
            )
            self._eligibility(context, player, registration, club, status)

    def _transfer_states(self, context):
        for index, status in enumerate(UnionPlayerTransfer.Status.values, 1):
            clubs = context["clubs"]
            source_club = clubs[index % len(clubs)]
            destination_club = clubs[(index + 1) % len(clubs)]
            player = self._player(
                context, "TRANSFER", index, UnionPlayer.Status.APPROVED
            )
            source = self._registration(
                context,
                player,
                source_club,
                f"TRANSFER_{status}",
                UnionPlayerRegistration.Status.ACTIVE,
            )
            UnionPlayerTransfer.objects.update_or_create(
                workspace=context["workspace"],
                player=player,
                source_registration=source,
                defaults={
                    "destination_club": destination_club,
                    "status": status,
                    "submitted_at": (
                        None
                        if status == UnionPlayerTransfer.Status.DRAFT
                        else timezone.now()
                    ),
                    "effective_on": timezone.localdate() + timedelta(days=index),
                    "transfer_type": (
                        "LOAN"
                        if status == UnionPlayerTransfer.Status.LOAN_ACTIVE
                        else "PERMANENT"
                    ),
                    "loan_end_on": (
                        timezone.localdate() + timedelta(days=90)
                        if status == UnionPlayerTransfer.Status.LOAN_ACTIVE
                        else None
                    ),
                    "initiated_by": context["actor"],
                    "documents": [{"demo_key": DEMO_KEY}],
                    "automatic_validation": {"demo_key": DEMO_KEY},
                    "decision_reason": f"Coverage transfer state: {status}.",
                    "change_request_reason": (
                        "Coverage changes required."
                        if status == UnionPlayerTransfer.Status.CHANGES_REQUESTED
                        else ""
                    ),
                },
            )

    def _affiliation_states(self, context):
        clubs = self._clubs_for_statuses(
            context,
            len(ClubAffiliation.Status.values),
        )
        for club, status in zip(clubs, ClubAffiliation.Status.values):
            ClubAffiliation.objects.update_or_create(
                workspace=context["workspace"],
                club=club,
                defaults={
                    "status": status,
                    "compliance_status": (
                        "COMPLIANT"
                        if status == ClubAffiliation.Status.ACTIVE
                        else "REVIEW_REQUIRED"
                    ),
                    "compliance_notes": f"{DEMO_KEY}:{status}",
                    "liaison": context["actor"],
                },
            )

    def _application_states(self, context):
        for index, status in enumerate(UnionRegistrationApplication.Status.values, 1):
            self._application(context, 100 + index, status)

    def _approval_states(self, context):
        players = list(
            UnionPlayer.objects.filter(
                union=context["workspace"].related_union,
                metadata__demo_key=DEMO_KEY,
            ).order_by("id")
        )
        for index, status in enumerate(UnionApproval.Status.values):
            self._approval(context, players[index].id, f"COVERAGE_{status}", status)

    def _team_states(self, context):
        player = UnionPlayer.objects.filter(
            union=context["workspace"].related_union,
            metadata__demo_key=DEMO_KEY,
            status=UnionPlayer.Status.APPROVED,
        ).first()
        member_statuses = list(NationalTeamMember.Status.values)
        for index, status in enumerate(NationalTeam.Status.values, 1):
            team, _ = NationalTeam.objects.update_or_create(
                workspace=context["workspace"],
                slug=f"{context['workspace'].slug}-coverage-{status.lower()}",
                defaults={
                    "name": f"Coverage {status.title()} Team",
                    "category": "Representative",
                    "status": status,
                    "notes": f"{DEMO_KEY}:{status}",
                    "is_active": status != NationalTeam.Status.INACTIVE,
                    "created_by": context["actor"],
                },
            )
            NationalTeamMember.objects.update_or_create(
                team=team,
                full_name=f"Coverage Member {index}",
                member_type=NationalTeamMember.MemberType.PLAYER,
                defaults={
                    "player": player,
                    "club": context["clubs"][index % len(context["clubs"])],
                    "role": "Player",
                    "status": member_statuses[(index - 1) % len(member_statuses)],
                    "notes": DEMO_KEY,
                },
            )

    def _assignment_states(self, context):
        matches = list(
            Match.objects.filter(
                competition__league__union=context["workspace"].related_union,
            ).order_by("id")
        )
        roles = list(UnionMatchOfficial.RoleType.values)
        for index, status in enumerate(FixtureOfficialAssignment.Status.values):
            official = self._official(context, status.lower(), roles[index])
            FixtureOfficialAssignment.objects.update_or_create(
                match=matches[index % len(matches)],
                official=official,
                role_type=roles[index],
                defaults={
                    "status": status,
                    "notes": f"{DEMO_KEY}:{status}",
                    "response_note": f"Coverage response: {status}",
                    "responded_at": (
                        timezone.now()
                        if status
                        in {
                            FixtureOfficialAssignment.Status.ACCEPTED,
                            FixtureOfficialAssignment.Status.DECLINED,
                        }
                        else None
                    ),
                    "assigned_by": context["actor"],
                },
            )

    def _governance_records(self, context):
        player = UnionPlayer.objects.filter(
            union=context["workspace"].related_union,
            metadata__demo_key=DEMO_KEY,
        ).first()
        for suffix in ["identity", "registration", "eligibility", "transfer"]:
            self._comment(context, "union_player", player.id, suffix)
            self._document(context, "union_player", player.id, suffix)
            self._audit(context, f"coverage.{suffix}", player.id)

    def _player(self, context, prefix, index, status):
        number = f"{context['workspace'].acronym}-COV-{prefix}-{index:03d}"
        player, _ = UnionPlayer.objects.update_or_create(
            union=context["workspace"].related_union,
            union_player_number=number,
            defaults={
                "first_name": f"Coverage{index}",
                "last_name": prefix.title(),
                "date_of_birth": date(1990 + index % 10, index % 12 + 1, 1),
                "nationality": "Ugandan",
                "identity_reference": f"ID-{number}",
                "status": status,
                "identity_verified_at": (
                    timezone.now() if status == UnionPlayer.Status.APPROVED else None
                ),
                "identity_verified_by": (
                    context["actor"] if status == UnionPlayer.Status.APPROVED else None
                ),
                "metadata": {
                    "demo_key": DEMO_KEY,
                    "coverage_status": status,
                },
            },
        )
        return player

    def _registration(self, context, player, club, key, status):
        registration, _ = UnionPlayerRegistration.objects.update_or_create(
            workspace=context["workspace"],
            player=player,
            registration_type=f"COVERAGE_{key}"[:40],
            defaults={
                "club": club,
                "season": context["season"],
                "status": status,
                "effective_from": date(2026, 1, 1),
                "approved_by": context["actor"],
                "approved_at": timezone.now(),
                "notes": DEMO_KEY,
                "decision_reason": f"Coverage registration state: {status}.",
            },
        )
        return registration

    def _eligibility(self, context, player, registration, club, status):
        eligibility, _ = UnionPlayerCompetitionEligibility.objects.update_or_create(
            player=player,
            competition_edition=context["edition"],
            defaults={
                "workspace": context["workspace"],
                "registration": registration,
                "club": club,
                "competition_identity": context["identity"],
                "season": context["season"],
                "status": status,
                "warnings": [f"Coverage state: {status}"],
                "restriction_reason": (
                    ""
                    if status == UnionPlayerCompetitionEligibility.Status.ELIGIBLE
                    else f"Coverage restriction: {status}"
                ),
                "reviewed_by": context["actor"],
                "reviewed_at": timezone.now(),
                "decision_reason": f"Coverage eligibility state: {status}.",
            },
        )
        return eligibility

    def _application(self, context, index, status):
        types = list(UnionRegistrationApplication.ApplicationType.values)
        application, _ = UnionRegistrationApplication.objects.update_or_create(
            workspace=context["workspace"],
            registration_number=f"{context['workspace'].acronym}-APP-{index:03d}",
            defaults={
                "application_type": types[(index - 1) % len(types)],
                "club": context["clubs"][index % len(context["clubs"])],
                "competition": context["competition"],
                "applicant_name": f"Coverage Applicant {index}",
                "status": status,
                "documents_complete": status
                == UnionRegistrationApplication.Status.APPROVED,
                "submitted_by": context["actor"],
                "reviewed_by": context["actor"],
                "reviewed_at": timezone.now(),
                "reviewer_notes": f"Coverage application state: {status}.",
                "metadata": {"demo_key": DEMO_KEY, "coverage_status": status},
            },
        )
        return application

    def _approval(self, context, subject_id, action, status):
        approval, _ = UnionApproval.objects.update_or_create(
            workspace=context["workspace"],
            subject_type="coverage_record",
            subject_id=subject_id,
            action=action,
            defaults={
                "status": status,
                "requested_by": context["actor"],
                "reviewed_by": context["actor"],
                "reason": DEMO_KEY,
                "decision_reason": f"Coverage approval state: {status}.",
                "metadata": {"demo_key": DEMO_KEY, "coverage_status": status},
                "reviewed_at": timezone.now(),
            },
        )
        return approval

    def _official(self, context, suffix, role_type):
        sport = context["workspace"].sport.upper()
        primary_sport = (
            UnionMatchOfficial.SportType.BASKETBALL
            if "BASKETBALL" in sport
            else (
                UnionMatchOfficial.SportType.FOOTBALL
                if "FOOTBALL" in sport
                else UnionMatchOfficial.SportType.RUGBY
            )
        )
        official, _ = UnionMatchOfficial.objects.update_or_create(
            union=context["workspace"].related_union,
            email=(
                f"{context['workspace'].slug}."
                f"{slugify(suffix)}.official@leagueos.test"
            ),
            defaults={
                "full_name": f"Coverage {suffix.title()} Official",
                "role_type": role_type,
                "certification_level": "Coverage Level 2",
                "primary_sport": primary_sport,
                "status": UnionMatchOfficial.Status.AVAILABLE,
                "notes": DEMO_KEY,
                "created_by": context["actor"],
            },
        )
        return official

    def _comment(self, context, subject_type, subject_id, suffix):
        body = f"[{DEMO_KEY}] {suffix} review comment."
        UnionReviewComment.objects.update_or_create(
            workspace=context["workspace"],
            subject_type=subject_type,
            subject_id=subject_id,
            body=body,
            defaults={"author": context["actor"], "is_internal": True},
        )

    def _document(self, context, subject_type, subject_id, suffix):
        UnionDocumentReference.objects.update_or_create(
            workspace=context["workspace"],
            subject_type=subject_type,
            subject_id=subject_id,
            document_type=f"COVERAGE_{suffix.upper()}",
            defaults={
                "title": f"Coverage {suffix.title()} Document",
                "file_url": f"https://example.test/{suffix}.pdf",
                "uploaded_by": context["actor"],
                "metadata": {"demo_key": DEMO_KEY},
            },
        )

    def _audit(self, context, action, target_id):
        if not UnionAuditEvent.objects.filter(
            workspace=context["workspace"],
            action=action,
            target_type="union_player",
            target_id=target_id,
            metadata__demo_key=DEMO_KEY,
        ).exists():
            UnionAuditEvent.objects.create(
                workspace=context["workspace"],
                actor=context["actor"],
                action=action,
                target_type="union_player",
                target_id=target_id,
                metadata={"demo_key": DEMO_KEY},
            )

    def _clubs_for_statuses(self, context, required):
        clubs = list(context["clubs"])
        sport_name = context["workspace"].sport.upper()
        sport = (
            Club.Sport.BASKETBALL
            if "BASKETBALL" in sport_name
            else Club.Sport.FOOTBALL if "FOOTBALL" in sport_name else Club.Sport.RUGBY
        )
        while len(clubs) < required:
            index = len(clubs) + 1
            club, _ = Club.objects.update_or_create(
                slug=f"{context['workspace'].slug}-coverage-club-{index}",
                defaults={
                    "name": f"Coverage Club {index} {context['workspace'].acronym}",
                    "short_name": f"COV{index}",
                    "sport": sport,
                },
            )
            clubs.append(club)
        return clubs
