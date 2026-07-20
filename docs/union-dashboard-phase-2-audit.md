# Union Dashboard Phase 2: Final Backend Implementation Audit

Audit date: 2026-07-20

Repository: `ufe-league-os-backend`

Branch: `feature/union-dashboard-phase-2`

Develop baseline: `596f11f`

Local Phase 2 checkpoint: `1907034`

## Executive conclusion

The completed Phase 2 registration, competition-eligibility, and transfer
backend is ready for frontend integration and commit review. The final focused
suite passes 310 tests. The Union foundation suite passes 34 tests. The full
backend suite passes 621 tests.

The final integration audit found one test-integration defect and no production
workflow defect. Two older tests still expected direct broad legacy player and
transfer creation. They were updated to assert the already-implemented safe
compatibility behavior: legacy POST creates a maintained inactive `DRAFT`,
never an approved registration or direct legacy transfer. No production code
was changed for this audit correction.

There are no verified P0 backend blockers. Migrations are additive and ordered,
but the persistent local Compose database has not applied Phase 2 migrations;
production and staging must apply reviewed migrations before commands or HTTP
traffic use the new tables. Both schedulers passed dry-run validation against
an isolated fully migrated database.

## Completed Phase 2 scope

- Active Union workspace membership, exact role/effective permissions, and
  resource scope restrictions.
- Shared Union approvals, append-only audit events, review comments, and
  document references.
- Permanent competition identities and season editions.
- Permanent Union player identity and deterministic player number allocation.
- Club registration draft, update, submit, resubmit, withdraw, restricted
  player search, and structured validation.
- Union registration reviewer assignment, review start, changes request,
  rejection, approval, renewal, competition registration, and replay.
- Read-only authoritative registration history.
- Competition eligibility creation, approval, rejection, suspension,
  reinstatement, expiry, cancellation, validation, and replay.
- Destination Club transfer draft/update, submission/resubmission, source Club
  response, direct/verified-offline consent or decline, cancellation, and
  prerequisite progression.
- Union transfer changes request, rejection, approval, immediate/scheduled
  permanent/free movement, loan activation, loan expiry, return-to-source, and
  completed replay.
- Explicit Club and Union APIs, privacy-safe serializers, legacy compatibility,
  post-commit notifications, and command-only scheduled processing.

## Models and migrations

The implementation retains domain ownership:

- `teams.PlayerRegistration` is the Club submission/legacy roster anchor.
- `dashboards.UnionPlayer` is the permanent Union identity.
- `dashboards.UnionPlayerRegistration` is immutable-period authoritative Club
  registration history.
- `dashboards.UnionPlayerCompetitionEligibility` is edition-specific
  eligibility history.
- `dashboards.UnionPlayerTransfer` owns the maintained transfer lifecycle.
- `UnionApproval`, `UnionAuditEvent`, `UnionReviewComment`, and
  `UnionDocumentReference` own shared governance evidence.

Migration chain:

```text
teams.0002

dashboards.0010
dashboards.0011
dashboards.0012
dashboards.0013
dashboards.0014
dashboards.0015
dashboards.0016
dashboards.0017
dashboards.0018
dashboards.0019
```

`makemigrations --check` reports no changes. `showmigrations` confirms the
chain without collision. The local persistent database currently has
`dashboards.0001–0009` and `teams.0001` applied; `migrate --plan` orders the
additive Phase 2 operations correctly. No existing migration was edited and no
new migration was created during the final audit.

## Service-layer status

All maintained state transitions use service-layer validation. Registration
and transfer state transitions use `transaction.atomic()` and row locks where
concurrency can change legal state. Authoritative registration and eligibility
movement is not implemented in views.

Replay paths are constrained by authoritative links and conditional
uniqueness:

- approval replay returns the existing registration;
- requested eligibility rows are resolved, not duplicated;
- transfer replay resolves the existing destination/return history;
- irreversible audit and notification work is not repeated;
- loan return validates frozen lineage and the exact eligibility set.

Notifications are registered with `transaction.on_commit()`. Notification
failure cannot roll back completed domain transitions. Activation and return
remain service-owned and are callable by management commands, not HTTP.

## API status and route integrity

The exact integration and route inventory is documented in:

```text
docs/api-contracts/union-dashboard-phase-2-api.md
```

Verified route families:

- Club registration submissions and restricted player search;
- legacy player read/update and maintained-draft POST compatibility;
- Union registration review and authoritative registration reads;
- Union eligibility list/detail/actions;
- Club transfer submissions and mixed-actor actions;
- Union transfer review and decisions;
- related read-only legacy transfer history and maintained-draft POST bridge.

The `teams` and `dashboards` URL modules contain no duplicate route name.
Static action paths do not shadow numeric detail paths. Maintained and legacy
numeric IDs cannot collide across separate route families. There is no direct
HTTP activation, loan-return, registration-movement, eligibility-movement, or
processor endpoint.

## Permissions and scope

The audit verified these contracts:

| Operation | Permission |
| --- | --- |
| Union dashboard | `union.dashboard.view` |
| Competition reads | `union.competitions.view` |
| Competition writes | `union.competitions.manage` |
| Club reads | `union.clubs.view` |
| Club writes | `union.clubs.manage` |
| Registration submission reads | `union.registrations.view` |
| Registration review management | `union.registrations.manage` |
| Player/authoritative registration reads | `union.players.view` |
| Registration/eligibility decisions | `union.players.approve` |
| Transfer reads | `union.transfers.view` |
| Transfer decisions | `union.transfers.approve` |
| Club transfer management | `club.transfers.manage` |

List/detail access is not replaced by approval permission. View-only access
cannot perform decisions. Ordinary Union users require active membership in an
active workspace. Club, source/destination Club, competition identity, and
competition edition scopes are independently enforced. Cross-workspace and
out-of-resource-scope lookups return nondisclosing errors. Super Admin
permission bypass retains resource/workspace relationship checks.

## Security and privacy findings

Repository searches and contextual review found:

- no `fields = "__all__"` serializer;
- maintained workflow serializers use explicit fields;
- no active broad `PlayerTransferSerializer` or
  `PlayerRegistrationSerializer`;
- the unsafe legacy `approve_player_transfer` function remains disabled and is
  not called by production code;
- Club APIs cannot make Union decisions;
- Union APIs cannot edit Club-controlled drafts;
- legacy routes cannot bypass maintained submission/review services;
- maintained history has no hard-delete route;
- querysets use the required `select_related`/`prefetch_related` graphs for
  scoped list/detail responses.

API responses exclude `activation_plan`, `return_plan`, permanent-player
identity references, offline evidence references, audit metadata, notification
internals, and processor failure details. Transfer and eligibility responses
do not expose player date of birth. Offline evidence is write-only.

## Legacy compatibility

Legacy player reads remain Club scoped. Legacy player PATCH permits only safe
Club-maintained fields. Legacy player POST is deprecated and creates an
inactive maintained registration `DRAFT`; it never creates approved
eligibility.

Legacy transfer history is related-Club read-only. Legacy transfer POST is
deprecated and creates only a maintained `UnionPlayerTransfer` `DRAFT`; it
creates no `teams.PlayerTransfer`. Legacy transfer detail supports GET only.
The broad writable legacy transfer serializer is absent.

## Scheduled command readiness

Implemented commands:

```text
python manage.py process_scheduled_player_transfers
python manage.py process_due_player_loan_returns
```

Both support `--as-of YYYY-MM-DD`, positive `--limit`, and `--dry-run`.
`--help` loads successfully. Direct dry runs against the persistent Compose
database correctly fail until Phase 2 migrations are applied. Without changing
that database, each command was then run against an isolated in-memory database
after the complete migration chain:

```text
Dry run as of 2026-07-20: 0 transfer(s) due.
Transfer IDs: []

Dry run as of 2026-07-20: 0 loan(s) due.
Transfer IDs: []
Effective return dates: []
```

Production should schedule each command daily only after migration deployment.

## Union navigation coverage

| Section | Classification | Finding |
| --- | --- | --- |
| Overview | COMPLETE | Real workspace/operations aggregation and tests |
| Competitions | COMPLETE | Identity, edition, league/season, membership and fixture contracts |
| Clubs | COMPLETE | Club, affiliation and league-membership management |
| Registrations | COMPLETE | Club submission, Union review and authoritative history |
| Players & Transfers | COMPLETE | Identity, eligibility, transfer APIs, activation and return |
| National Teams | COMPLETE | Current workspace-scoped team/member CRUD |
| Match Officials | COMPLETE | Readiness, official, appointment and response contracts |
| Statistics & Records | MISSING | No dedicated Union records business contract |
| Finance | PARTIAL | Workspace summary exists; accounting workflows do not |
| Communications | MISSING | Generic notifications are not a Union broadcast contract |
| Sponsors | EXISTING_LEGACY_ONLY | Sponsorship domain is not yet Union-workspace integrated |
| Users & Access | PARTIAL | Existing list/create/switch/owner; full membership lifecycle absent |
| Audit & Approvals | COMPLETE | Shared approvals, events, comments and documents |
| Settings | FRONTEND_ONLY_GAP | No approved writable settings contract |

Details and future-ticket priorities are in:

```text
docs/codex-handoffs/union-dashboard-backend-gap-register.md
```

## Verified defects found and fixed

Found:

1. `teams.tests.PlayerRegistrationTests.test_create_player_registration`
   expected the pre-Phase-2 direct creation behavior.
2. `teams.tests.PlayerTransferTests.test_create_transfer` expected a direct
   broad legacy transfer write.

Fixed:

- Added the governing workspace relationship and asserted the safe deprecated
  player POST creates an inactive `DRAFT`.
- Added active source/destination Club scope and authoritative registration
  setup and asserted the deprecated transfer POST creates one maintained
  transfer `DRAFT` and no legacy transfer row.

The focused corrected classes pass. No production implementation change was
needed.

## Verification

- Final focused Phase 2 suite: **310 tests passed**.
- Union foundation suite: **34 tests passed**.
- Corrected legacy integration classes: **2 tests passed**.
- Full backend suite: **621 tests passed in 589.156 seconds**.
- Django check: no issues.
- Migration check: no changes detected.
- Black: 325 files unchanged.
- Ruff: all checks passed.
- Final Git integrity results are recorded in
  `docs/codex-handoffs/union-dashboard-phase-2-current.md`.

## Known limitations

- Phase 2 migrations are not applied to the persistent local Compose database.
- Production daily scheduling is not configured in this repository.
- Registration validation explicitly reports unavailable fee, suspension,
  squad-limit, transfer-window, dual-registration, foreign-player, and
  cup-tied rule engines where applicable.
- Statistics/records, Union communications, Union sponsorship integration,
  full Union accounting, membership lifecycle, and writable settings need
  separately approved business contracts.
- Frontend integration has not been performed in this backend-only ticket.

## Frontend readiness

Registrations and Players & Transfers are ready for frontend integration
against the versioned entitlement/workspace context and the documented Phase 2
API. Competitions, Clubs, Overview, current National Teams, current Match
Officials, and Audit & Approvals also have existing backend contracts.
Unavailable sections must render a capability state rather than fabricated
data or mutations.

## Merge readiness

Backend code is merge-ready subject to Keith's diff/commit review and the
logical atomic staging described in:

```text
docs/codex-handoffs/union-dashboard-phase-2-commit-plan.md
```

The working tree is intentionally uncommitted and unstaged. Deployment
readiness additionally requires applying reviewed migrations in staging,
running smoke tests, and configuring/monitoring the two daily commands.

## Historical baseline context

The original Phase 2 baseline correctly identified reusable Union workspace,
league, competition, Club, national-team, official, registration, account,
audit, payment, notification, and sponsorship capabilities. It proposed:

1. shared Union scope/governance services;
2. permanent competition identity and season editions;
3. transactional registration, player identity, eligibility, and transfer
   history;
4. operational commands and explicit APIs;
5. frontend replacement of placeholders only when authenticated backend data
   exists.

Phase 2 completed the first three foundations and the player/transfer slice of
the fourth. Finance, communications, Union sponsorship, records, complete user
administration, and settings remain deliberately recorded as future work
rather than speculative additions.
