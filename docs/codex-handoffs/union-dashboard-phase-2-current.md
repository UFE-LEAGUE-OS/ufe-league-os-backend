# Union Dashboard Phase 2 — Current Codex Handoff

## Handoff metadata

- Updated: 2026-07-20
- Repository: `ufe-league-os-backend`
- Branch: `feature/union-dashboard-phase-2`
- Working tree: uncommitted Phase 2 changes; no files staged
- Frontend changed: No
- Commit, push, merge, or deployment performed: No

## Completed Phase 2 foundation

The backend now has maintained contracts for Union workspaces, competition
identities and editions, permanent Union player identities, Club-owned player
registration submissions, restricted player-registry search, structured
pre-submission validation, Union review decisions, and authoritative
registration history. Legacy roster records remain readable and safely
maintainable without allowing the legacy routes to bypass the submission
workflow.

Competition-eligibility decisions remain deliberately outside this slice.

## Models and migrations

### `teams/0002`

`backend/teams/migrations/0002_playerregistration_assigned_reviewer_and_more.py`
adds the Club submission lifecycle to `teams.PlayerRegistration`. The migration
is additive and preserves existing roster rows as `LEGACY`.

The maintained submission fields are:

- `submission_status`
- `registration_type`
- `union_workspace`
- `union_player`
- `season_record`
- `requested_competition_editions`
- `submitted_by`
- `submitted_at`
- `last_resubmitted_at`
- `assigned_reviewer`
- `change_request_reason`
- `union_decision_reason`
- `reviewed_at`
- `supporting_documents`
- `club_notes`
- `automatic_validation`
- `submission_revision`
- `withdrawal_reason`

Submission statuses are `LEGACY`, `DRAFT`, `SUBMITTED`,
`UNDER_AUTOMATIC_REVIEW`, `UNDER_UNION_REVIEW`, `CHANGES_REQUESTED`,
`APPROVED`, `REJECTED`, `WITHDRAWN`, and `EXPIRED`.

### Union player and competition migrations

- `dashboards/0010` adds workspace scope restrictions and related governance
  fields.
- `dashboards/0011` adds permanent competition identities and season editions.
- `dashboards/0012` adds the permanent `UnionPlayer` identity foundation.
- `dashboards/0013` adds the locked per-Union player-number sequence.
- `dashboards/0014` extends authoritative `UnionPlayerRegistration` history and
  adds `UnionPlayerCompetitionEligibility`.
- `dashboards/0015` adds the nullable
  `UnionPlayerCompetitionEligibility.source_submission` relationship and a
  conditional unique constraint on source submission plus competition
  edition. Existing eligibility rows require no backfill and remain intact.

## Club submission services

`backend/teams/player_submission_services.py` contains the Club-owned workflow:

- `create_player_registration_draft`
  - resolves one eligible active Union workspace;
  - rejects ambiguous or unrelated workspace selection;
  - creates or safely selects a Union player identity;
  - creates an inactive roster row with `submission_status=DRAFT`;
  - validates requested edition scope;
  - writes `player_registration.draft_created`.
- `update_player_registration_draft`
  - locks the row;
  - allows only `DRAFT` or `CHANGES_REQUESTED`;
  - rejects Club-controlled decision fields;
  - safely validates and applies many-to-many edition updates;
  - writes `player_registration.draft_updated`.
- `submit_player_registration`
  - locks and freshly validates a `DRAFT`;
  - stores `automatic_validation`;
  - preserves state when validation blocks;
  - otherwise timestamps, increments the revision, and writes
    `player_registration.submitted`.
- `resubmit_player_registration`
  - locks and freshly validates `CHANGES_REQUESTED`;
  - replaces stale validation;
  - preserves the original `submitted_at`;
  - sets `last_resubmitted_at`, increments the revision, and writes
    `player_registration.resubmitted`.
- `withdraw_player_registration`
  - locks the row;
  - requires a reason;
  - permits only Club-controlled pre-review states;
  - never deletes the registration;
  - writes `player_registration.withdrawn`.

## Restricted Union player search

`search_union_players_for_club` requires an actively administered Club and
resolves only a workspace that governs that Club. It requires a meaningful
name/player-number query or exact date of birth, is limited to the selected
Union, defaults to 20 results, and rejects limits above 50.

The response contract exposes only:

- identity ID and Union player number;
- name, date of birth, nationality, and status;
- `can_be_selected` and `selection_warning`;
- a minimal current Club summary derived only from an active maintained
  `UnionPlayerRegistration`.

Identity references, metadata, verification evidence, documents, audit data,
and other Club submissions are not exposed.

## Structured validation contract

`validate_player_registration_submission` returns:

```json
{
  "blocking_errors": [],
  "review_warnings": [],
  "passed_checks": [],
  "capability_notes": [],
  "evaluated_at": "ISO-8601 timestamp",
  "version": 1
}
```

Every item has `code`, `field`, `message`, and `severity`.

Maintained blocking checks cover:

- active Club scope and governing workspace;
- team-to-Club relationship;
- season presence and Union scope;
- non-empty supporting-document references;
- player identity presence, Union scope, and blocked identity statuses;
- competition-edition Union and season scope;
- registration-date order;
- supported registration type;
- duplicate non-terminal Club/player/season submissions;
- duplicate registration numbers.

Warnings identify provisional or pending identities, registration history,
missing edition requests, and limited dual-registration rules. Capability notes
explicitly report unavailable fee, detailed suspension, transfer-window, and
squad-limit checks.

Submit and resubmit store the complete result and write
`player_registration.validation_completed`. Its audit metadata contains only:

- `blocking_error_count`
- `review_warning_count`
- `capability_note_count`
- `validation_version`

Blocked transitions return the structured result, retain their prior status,
do not increment revisions, and do not set new submission timestamps.

## Explicit serializers

The Club and compatibility APIs use explicit serializers:

- `ClubPlayerRegistrationDraftCreateSerializer`
- `ClubPlayerRegistrationDraftUpdateSerializer`
- `ClubPlayerRegistrationSubmissionListSerializer`
- `ClubPlayerRegistrationSubmissionDetailSerializer`
- `ClubPlayerRegistrationWithdrawSerializer`
- `ClubPlayerRegistrationDecisionSerializer`
- `ClubPlayerRegistrySearchQuerySerializer`
- `ClubPlayerRegistrySearchSerializer`
- `LegacyPlayerRegistrationReadSerializer`
- `LegacyPlayerRegistrationUpdateSerializer`
- `PlayerRegistrationSummarySerializer`

There is no active `PlayerRegistrationSerializer` reference and no broad
writable player-registration serializer usage.

## Club submission API routes

- `GET|POST /api/teams/player-registration-submissions/`
- `GET|PATCH /api/teams/player-registration-submissions/<id>/`
- `POST /api/teams/player-registration-submissions/<id>/submit/`
- `POST /api/teams/player-registration-submissions/<id>/resubmit/`
- `POST /api/teams/player-registration-submissions/<id>/withdraw/`
- `GET /api/teams/player-registration-submissions/<id>/decision/`
- `GET /api/teams/player-registry-search/`

All record lookups are Club-scoped. Another Club's record returns `404` where
resource disclosure would otherwise occur. Submission detail routes do not
support `PUT` or `DELETE`.

## Legacy route compatibility

`GET /api/teams/players/` remains a Club-scoped roster summary for both
preserved `LEGACY` rows and workflow records. The summary includes both roster
`status` and `submission_status`.

`POST /api/teams/players/` is now a deprecated compatibility entry point. It:

- validates with `ClubPlayerRegistrationDraftCreateSerializer`;
- calls `create_player_registration_draft`;
- creates an inactive `DRAFT`, never an approved or eligible registration;
- returns `201` with `workflow=PLAYER_REGISTRATION_SUBMISSION`,
  `deprecated_direct_creation=true`, and the explicit submission detail;
- writes the normal draft-created audit event with
  `source_route=legacy_players_post`;
- rejects status, user, workspace/player identity, reviewer, decision,
  validation, and revision fields controlled by the server or Union.

`GET /api/teams/players/<id>/` returns the explicit read-only legacy
representation for a `LEGACY` row and the explicit submission detail for a
workflow row. Cross-Club records return `404`.

`PATCH /api/teams/players/<id>/` routes workflow records through
`update_player_registration_draft`. A `LEGACY` row uses
`LegacyPlayerRegistrationUpdateSerializer`, which permits only safe
Club-maintained roster fields and cannot alter Club, registration number,
status, workflow state, identity, or Union decision data.

The legacy detail route supports only `GET` and `PATCH`. `PUT` and `DELETE`
return `405`; hard deletion is unavailable.

## Audit events

The completed Club workflow writes:

- `union_player.existing_identity_selected`
- `player_registration.draft_created`
- `player_registration.draft_updated`
- `player_registration.validation_completed`
- `player_registration.submitted`
- `player_registration.resubmitted`
- `player_registration.withdrawn`

Audit metadata does not contain document content or private player identity
evidence.

## Union player-registration review

`backend/dashboards/union_player_review_services.py` implements locked,
transactional transitions for:

- reviewer assignment from `SUBMITTED` or `UNDER_UNION_REVIEW`;
- review start from `SUBMITTED` to `UNDER_UNION_REVIEW`;
- request changes from `UNDER_UNION_REVIEW` to `CHANGES_REQUESTED`;
- rejection from `UNDER_UNION_REVIEW` to `REJECTED`, with the legacy roster
  status set to `INACTIVE`;
- approval from `UNDER_UNION_REVIEW` to `APPROVED`, with the legacy roster
  status set to `ACTIVE`.

Every transition uses `transaction.atomic()` and `select_for_update()`.
Reviewer assignment and review management require
`union.registrations.manage`; final approval and rejection require
`union.players.approve`. List/detail access requires
`union.registrations.view`, and authoritative registration reads require
`union.players.view`.

All ordinary users require an active membership in the explicitly selected
active workspace. GET requests use the `workspace` query parameter and POST
requests use the `workspace` request field. Club, requested competition
identity, and requested competition edition restrictions are enforced in
lists and independently in detail/action lookups. Out-of-workspace,
out-of-scope, missing, and legacy submission detail lookups do not disclose
record existence.

The shared maintained validation core remains in
`backend/teams/player_submission_services.py`. The Club validator still adds
the Club-administrator check. The new Union validator adds membership,
permission, workspace, scope, review state, self-review, authoritative
registration conflict, renewal, competition-registration, and
dual-registration checks. Review start and final decisions always store fresh
structured validation. Warnings do not block review or approval; blocking
errors prevent approval.

## Union review API routes

- `GET /api/dashboards/union-admin/player-registration-submissions/`
- `GET /api/dashboards/union-admin/player-registration-submissions/<id>/`
- `POST /api/dashboards/union-admin/player-registration-submissions/<id>/assign-reviewer/`
- `POST /api/dashboards/union-admin/player-registration-submissions/<id>/start-review/`
- `POST /api/dashboards/union-admin/player-registration-submissions/<id>/request-changes/`
- `POST /api/dashboards/union-admin/player-registration-submissions/<id>/approve/`
- `POST /api/dashboards/union-admin/player-registration-submissions/<id>/reject/`
- `GET /api/dashboards/union-admin/player-registrations/`
- `GET /api/dashboards/union-admin/player-registrations/<id>/`

Submission lists exclude `LEGACY`, `DRAFT`, and `WITHDRAWN` by default and
support the maintained status, Club, team, season, type, reviewer, date,
search, and ordering filters. Authoritative registration endpoints are
read-only and independently enforce workspace and Club scope.

## Authoritative registration decisions

First and free-agent approval creates one active
`UnionPlayerRegistration`, links its source submission, and promotes a
provisional or pending-verification permanent player to `APPROVED` while
recording the identity verifier and timestamp.

Season renewal expires the previous same-Club active row, closes it on the day
before the new effective date, preserves it as history, and creates an active
successor linked through `predecessor`. Cross-Club, same-season, missing-active,
and invalid-date renewals are blocked.

Competition registration requires and reuses an active same-Club registration.
It does not create a second Club registration. Every registration approval
creates or resolves one pending eligibility row per requested competition
edition. No requested edition returns an empty eligibility result and
`eligibility_review_required=false`; eligibility is never fabricated. Dual
registration remains blocked with the maintained unavailable-rules message.

Approval replay resolves the existing authoritative row and returns
`idempotent_replay=true`. It creates no duplicate registration, identity
verification, eligibility, notification, or irreversible audit event.

The Union workflow writes:

- `player_registration.reviewer_assigned`
- `player_registration.review_started`
- `player_registration.validation_completed`
- `player_registration.changes_requested`
- `player_registration.approved`
- `player_registration.rejected`
- `union_player_registration.created`
- `union_player_registration.renewed`

Changes requested, approval, and rejection schedule a governance in-app
notification with `transaction.on_commit()`. Notification metadata contains
only submission ID, Club ID, and submission status. Notification failure does
not roll back the completed transition.

## Competition eligibility lifecycle

`backend/dashboards/union_player_eligibility_services.py` implements pending
creation, structured validation, approval, rejection, suspension,
reinstatement, expiry, and cancellation.

Pending creation validates the approved source submission, active
authoritative registration, player, Club, workspace Union, edition identity,
season, and Club/identity/edition scopes. It copies source validation warnings
and links the source submission and authoritative registration. Repeated calls
resolve the same source-submission/edition row without another audit event.

The legal transitions are:

- `PENDING → ELIGIBLE`, `REJECTED`, or `CANCELLED`;
- `ELIGIBLE → SUSPENDED` or `EXPIRED`;
- `SUSPENDED → ELIGIBLE` or `EXPIRED`.

Terminal rejected, cancelled, expired, and ineligible rows cannot be reopened.
Rows are never deleted or rewritten as a fresh application.

Eligibility validation uses the maintained version-1 structured schema. It
checks active membership and `union.players.approve`, workspace/resource
scope, approved player state, active matching registration, reviewable
competition edition and season, eligibility dates, and conflicting eligible
records. Source warnings, closed-after-submission state, missing teams, and
incomplete rule engines remain warnings. Squad limits, cup-tied rules,
disciplinary detail, payments, and foreign-player rules are explicit
capability notes.

Approval and reinstatement run fresh validation. Approval defaults dates
within the maintained registration and competition bounds and is idempotent.
Suspension affects only the selected edition and preserves the original
decision. Reinstatement retains the earlier audit history.

The lifecycle writes:

- `competition_eligibility.pending_created`
- `competition_eligibility.approved`
- `competition_eligibility.rejected`
- `competition_eligibility.suspended`
- `competition_eligibility.reinstated`
- `competition_eligibility.expired`
- `competition_eligibility.cancelled`

Approval, rejection, suspension, and reinstatement notify the original Club
submitter after commit. Metadata contains only eligibility, submission, Club,
edition, and status identifiers/values. Notification failures cannot roll back
decisions.

## Competition eligibility APIs

The eligibility API uses explicit list, detail, decision, approval, and
action-result serializers. List responses expose only concise player, Club,
registration, competition, season, source-submission, date, warning-count, and
review evidence. Detail adds maintained eligibility warnings and decision
fields without exposing identity references, supporting documents, unrelated
Club notes, audit metadata, or other applications.

The routes are:

- `GET /api/dashboards/union-admin/player-eligibilities/`
- `GET /api/dashboards/union-admin/player-eligibilities/<id>/`
- `POST /api/dashboards/union-admin/player-eligibilities/<id>/approve/`
- `POST /api/dashboards/union-admin/player-eligibilities/<id>/reject/`
- `POST /api/dashboards/union-admin/player-eligibilities/<id>/suspend/`
- `POST /api/dashboards/union-admin/player-eligibilities/<id>/reinstate/`
- `POST /api/dashboards/union-admin/player-eligibilities/<id>/expire/`
- `POST /api/dashboards/union-admin/player-eligibilities/<id>/cancel/`

GET requests require a `workspace` query parameter; actions require
`workspace` in the request body. Numeric workspace IDs and established
slug/acronym selections are supported. List/detail require
`union.players.view`; every action requires `union.players.approve`.

List results retain terminal history and support status, Club, team, player,
registration, source submission, competition identity, edition, season,
reviewer, created-date, search, and explicit safe ordering filters. Club,
identity, and edition restrictions filter lists and are independently enforced
as safe `404` responses on detail and action lookup.

Approval accepts a required reason and optional eligibility dates. Other
actions accept only a reason plus workspace. Blank reasons and reversed dates
return field-level `400` responses. Structured service validation failures
retain `automatic_validation`. Action responses consistently contain
`eligibility`, nullable `automatic_validation`, and `idempotent_replay`;
approval replay reports `true` without creating another row.

Direct list creation and detail `POST`, `PATCH`, `PUT`, or `DELETE` are not
available. Eligibility creation remains exclusively tied to approved Club
registration submissions, and lifecycle changes remain explicit actions.

## Focused tests and validation results

- Eligibility API focused command:
  `docker compose run --rm backend python manage.py test dashboards.test_union_player_eligibility_api -v 1`
- Result: **18 tests passed**, covering all 59 required API scenarios.
- Eligibility focused command:
  `docker compose run --rm backend python manage.py test dashboards.test_union_player_eligibility_services -v 1`
- Result: **21 tests passed**, covering all 55 required eligibility service and
  approval-integration scenarios.
- Union review focused command:
  `docker compose run --rm backend python manage.py test dashboards.test_union_player_registration_review -v 1`
- Result: **24 tests passed**, covering all 57 required review-contract
  scenarios.
- Combined service and registration regression command:
  `docker compose run --rm backend python manage.py test dashboards.test_union_player_eligibility_services dashboards.test_union_player_registration_review teams.test_player_registration_submissions dashboards.test_union_players -v 1`
- Result: **79 tests passed**: 21 eligibility service, 24 Union review, 31 Club
  submission, and 3 player foundation tests.
- Django check:
  `docker compose run --rm backend python manage.py check`
- Result: **System check identified no issues (0 silenced).**
- Migration check:
  `docker compose run --rm backend python manage.py makemigrations --check`
- Result: **No changes detected.**
- Migration plan:
  `docker compose run --rm backend python manage.py migrate --plan`
- Result: **Plan completed and includes additive dashboards migration 0015
  after dashboards 0014 and teams 0002.**
- Black checked the four API-scoped Python files.
- Result: **4 files would be left unchanged.**
- Ruff checked the four API-scoped Python files.
- Result: **All checks passed.**

Docker Compose continues to report the pre-existing orphan object-storage
container warning; it does not affect the test or validation results.

## Remaining Phase 2 work

- Complete Club/Union transfer APIs, consent, notifications, and eligibility
  recalculation in later slices.

## Recommended next implementation slice

Club-initiated player transfer submission lifecycle and actor boundaries.

## Prompt-ready context for ChatGPT

Continue on `feature/union-dashboard-phase-2` from the current uncommitted
backend working tree. Do not reset, stage, commit, push, merge, deploy, or touch
the frontend.

The completed contract uses `teams.PlayerRegistration` as the Club-owned
workflow anchor, `dashboards.UnionPlayer` as the permanent identity, and
`dashboards.UnionPlayerRegistration` as authoritative Club registration
history. Club submission and legacy compatibility services are complete.
Union-scoped list/detail/actions, fresh review validation, locked transitions,
first/free registration approval, season renewal, competition registration
reuse, idempotency, audit events, governance notifications, and read-only
authoritative registration APIs are implemented and tested. Registration
approval now creates idempotent pending eligibility rows for requested
editions. The complete eligibility service lifecycle, structured validation,
legal transitions, scopes, audit events, and notifications are implemented and
tested. Secure Union eligibility list/detail and explicit lifecycle decision
APIs are complete, scoped, read/write restricted, and tested.

Implement the next slice without redesigning those contracts:

1. Define Club-initiated player transfer drafts and submission transitions.
2. Establish explicit source-Club, destination-Club, player-consent, and Union
   reviewer actor boundaries.
3. Preserve authoritative registration and eligibility history until a
   transfer decision is approved transactionally.
4. Apply maintained Club and Union workspace scopes and permissions.
5. Add focused service tests before exposing transfer APIs.

Do not implement transfers, promotion/relegation, National Teams, officials,
statistics, finance, communications, sponsorship, or frontend work in that
slice.
