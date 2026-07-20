# Union Dashboard Phase 2 API Contract

Date: 2026-07-20

Branch: `feature/union-dashboard-phase-2`

Base path: `/api`

This document is the frontend integration contract for the completed Phase 2
player-registration, competition-eligibility, and player-transfer workflows.
All endpoints require authentication. Resource visibility is constrained by
the authenticated account, active workspace or Club scope, and the granular
permission required by the operation.

## Workspace rules

Union list and detail requests carry the selected workspace in the
`workspace` query parameter. Union action requests carry `workspace` in the
JSON body.

```text
GET /api/dashboards/union-admin/player-transfers/?workspace=ufa
POST /api/dashboards/union-admin/player-transfers/41/approve/
{"workspace": "ufa", "reason": "All transfer requirements are satisfied."}
```

Registration-review and eligibility endpoints accept an active workspace
slug or acronym. Transfer endpoints accept an active workspace numeric ID,
slug, or acronym. Frontend code should use the workspace slug consistently.
Workspace display names are not part of this contract.

- Missing workspace: `400` with `{"detail": "workspace is required."}` on
  transfer endpoints; other Union endpoint families fail closed through their
  workspace resolver.
- Inactive, unknown, or inaccessible workspace: `403` with a neutral active
  workspace access error.
- Workspace without a linked Union/Federation: `400`.
- Existing but out-of-scope records: `404`.
- Active workspace without the operation permission: `403`.
- Super Admin permission bypass does not bypass workspace/resource
  relationship validation.

Club endpoints do not trust a role string. They derive active Club authority
from the authenticated account. Transfer draft creation additionally requires
the numeric `workspace` and authoritative `source_registration`. Player
registration draft creation accepts optional numeric `union_workspace_id`;
when omitted, the service must resolve exactly one governing active workspace.

## Error and validation shapes

Ordinary request errors use DRF field errors or a neutral detail response:

```json
{
  "destination_club": ["This field is required."]
}
```

```json
{
  "detail": "Player transfer not found."
}
```

Submission and decision services can add `automatic_validation` without
flattening its structure:

```json
{
  "status": ["The transfer cannot be submitted."],
  "automatic_validation": {
    "version": 1,
    "blocking_errors": [],
    "review_warnings": [],
    "passed_checks": [],
    "capability_notes": [],
    "evaluated_at": "2026-07-20T12:00:00Z"
  }
}
```

Every structured validation item has `code`, `field`, `message`, and
`severity`. A transition with blocking errors does not advance state or
increment its revision.

## Status enums

Player-registration submission:

```text
LEGACY
DRAFT
SUBMITTED
UNDER_AUTOMATIC_REVIEW
UNDER_UNION_REVIEW
CHANGES_REQUESTED
APPROVED
REJECTED
WITHDRAWN
EXPIRED
```

Registration type:

```text
FIRST_REGISTRATION
SEASON_RENEWAL
COMPETITION_REGISTRATION
DUAL_REGISTRATION
FREE_AGENT_REGISTRATION
```

Authoritative registration:

```text
PENDING
CHANGES_REQUESTED
APPROVED
ACTIVE
TRANSFERRED
EXPIRED
SUSPENDED
REJECTED
CANCELLED
```

Competition eligibility:

```text
PENDING
ELIGIBLE
INELIGIBLE
SUSPENDED
EXPIRED
REJECTED
CANCELLED
```

Maintained transfer:

```text
DRAFT
SUBMITTED
PLAYER_CONSENT_REQUIRED
SOURCE_CLUB_RESPONSE_REQUIRED
UNDER_AUTOMATIC_REVIEW
UNDER_UNION_REVIEW
CHANGES_REQUESTED
APPROVED
REJECTED
CANCELLED
LOAN_ACTIVE
COMPLETED
EXPIRED
```

Transfer type is `PERMANENT`, `FREE_TRANSFER`, or `LOAN`. Source Club response
is `PENDING`, `ACKNOWLEDGED`, or `OBJECTED`. Player consent is `PENDING`,
`CONSENTED`, or `DECLINED`.

## Route inventory

### Club registration and player compatibility

| Method | Route | Contract |
| --- | --- | --- |
| GET, POST | `/api/teams/player-registration-submissions/` | Scoped list; create `DRAFT` |
| GET, PATCH | `/api/teams/player-registration-submissions/<id>/` | Read or update `DRAFT`/`CHANGES_REQUESTED` |
| POST | `/api/teams/player-registration-submissions/<id>/submit/` | Submit a `DRAFT` |
| POST | `/api/teams/player-registration-submissions/<id>/resubmit/` | Resubmit `CHANGES_REQUESTED` |
| POST | `/api/teams/player-registration-submissions/<id>/withdraw/` | Withdraw before Union review |
| GET | `/api/teams/player-registration-submissions/<id>/decision/` | Read Union decision evidence |
| GET | `/api/teams/player-registry-search/` | Restricted permanent-player search |
| GET, POST | `/api/teams/players/` | Legacy read; deprecated POST creates maintained `DRAFT` |
| GET, PATCH | `/api/teams/players/<id>/` | Legacy/workflow read; safe legacy or draft update |

Draft creation fields are `club`, `team`, `registration_number`, player
demographics and roster attributes, `registration_type`, `season_record`,
`requested_competition_editions`, `supporting_documents`, `club_notes`, and
optional write-only `identity_reference`, `existing_union_player_id`, and
`union_workspace_id`. The service owns identity selection, workspace,
submission status, reviewer, validation, revisions, and decisions.

Draft update omits Club, identity-selection fields, workspace, submission
state, reviewer, validation, revisions, and all Union decision fields.
Withdrawal requires:

```json
{"withdrawal_reason": "The Club needs to correct the source documents."}
```

Registry search requires `club` plus `q` or exact `date_of_birth`; optional
fields are `union_workspace_id` and `limit` (`1..50`, default `20`). Results
contain only the permanent player ID/number, name, date of birth, nationality,
status, selection flags, and a minimal current-Club summary.

The legacy POST response is:

```json
{
  "workflow": "PLAYER_REGISTRATION_SUBMISSION",
  "deprecated_direct_creation": true,
  "submission": {}
}
```

It never creates an approved or eligible registration. Legacy detail has no
`PUT` or `DELETE`.

### Union registration review

| Method | Route | Permission |
| --- | --- | --- |
| GET | `/api/dashboards/union-admin/player-registration-submissions/` | `union.registrations.view` |
| GET | `/api/dashboards/union-admin/player-registration-submissions/<id>/` | `union.registrations.view` |
| POST | `.../<id>/assign-reviewer/` | `union.registrations.manage` |
| POST | `.../<id>/start-review/` | `union.registrations.manage` |
| POST | `.../<id>/request-changes/` | `union.registrations.manage` |
| POST | `.../<id>/approve/` | `union.players.approve` |
| POST | `.../<id>/reject/` | `union.players.approve` |
| GET | `/api/dashboards/union-admin/player-registrations/` | `union.players.view` |
| GET | `/api/dashboards/union-admin/player-registrations/<id>/` | `union.players.view` |

Reviewer assignment accepts optional `reviewer`; omission lets the service use
its supported default. Request changes, approval, and rejection require a
non-empty `reason`. Union submission detail is read-only and may include
Club-submitted documents, notes, structured validation, reviewer evidence,
permanent-player summary, and authoritative-registration summary.

Approval/replay returns:

```json
{
  "submission": {},
  "authoritative_registration": {},
  "automatic_validation": {},
  "idempotent_replay": false,
  "eligibility_review_required": true
}
```

Authoritative registrations are read-only summaries of immutable-period
history. No view directly moves registration history.

### Competition eligibility

| Method | Route | Permission |
| --- | --- | --- |
| GET | `/api/dashboards/union-admin/player-eligibilities/` | `union.players.view` |
| GET | `/api/dashboards/union-admin/player-eligibilities/<id>/` | `union.players.view` |
| POST | `.../<id>/approve/` | `union.players.approve` |
| POST | `.../<id>/reject/` | `union.players.approve` |
| POST | `.../<id>/suspend/` | `union.players.approve` |
| POST | `.../<id>/reinstate/` | `union.players.approve` |
| POST | `.../<id>/expire/` | `union.players.approve` |
| POST | `.../<id>/cancel/` | `union.players.approve` |

All actions require `workspace` and a non-empty `reason`. Approval optionally
accepts `eligible_from` and `eligible_until` in `YYYY-MM-DD` form.

```json
{
  "workspace": "ufa",
  "reason": "Registration and edition rules are satisfied.",
  "eligible_from": "2026-08-01",
  "eligible_until": "2027-05-31"
}
```

Action responses use:

```json
{
  "eligibility": {},
  "automatic_validation": null,
  "idempotent_replay": false
}
```

Lists are concise. Detail includes maintained warnings, restriction/decision
reason, dates, source-submission evidence, and reviewer evidence. Eligibility
movement is service-owned; no direct movement endpoint exists.

### Club transfer workflow

| Method | Route | Contract |
| --- | --- | --- |
| GET, POST | `/api/teams/player-transfer-submissions/` | Mixed-actor scoped list; destination Club draft creation |
| GET, PATCH | `/api/teams/player-transfer-submissions/<id>/` | Scoped read; destination Club draft update |
| POST | `.../<id>/submit/` | Destination Club submission |
| POST | `.../<id>/resubmit/` | Destination Club resubmission |
| POST | `.../<id>/cancel/` | Destination Club pre-review cancellation |
| POST | `.../<id>/source-response/` | Source Club acknowledge/object |
| POST | `.../<id>/consent/` | Linked player direct consent |
| POST | `.../<id>/decline/` | Linked player direct decline |
| GET, POST | `/api/teams/transfers/` | Related legacy reads; deprecated POST creates maintained draft |
| GET | `/api/teams/transfers/<legacy_id>/` | Related legacy detail only |

Draft creation requires `workspace`, `source_registration`,
`destination_club`, `effective_on`, and `transfer_type`. Optional fields are
`destination_team`, `loan_end_on`, `documents`, and `fee_status`. Draft update
permits only the latter transfer terms; the service owns player, source Club,
status, prerequisite evidence, review, activation, registration, and
eligibility movement.

Cancellation requires `reason`. Source response requires:

```json
{
  "response_status": "ACKNOWLEDGED",
  "response": ""
}
```

`OBJECTED` requires a written response. Direct consent requires
`consent_method`; direct decline requires `reason`. Club administrators need
active Club scope and `club.transfers.manage`; the linked player is authorised
by relationship for direct consent/decline.

List responses use `{"count": 0, "results": []}`. Detail is read-only and may
include submitted documents, written prerequisite evidence, structured
validation, decisions, and timestamps. `PUT`, `DELETE`, Union decisions,
activation, return, and direct history movement are unavailable.

The deprecated legacy POST response is:

```json
{
  "workflow": "UNION_PLAYER_TRANSFER",
  "deprecated_direct_creation": true,
  "submission": {}
}
```

It creates no `teams.PlayerTransfer`. Maintained and legacy numeric IDs cannot
collide because they are resolved by separate route families.

### Union transfer review

| Method | Route | Permission |
| --- | --- | --- |
| GET | `/api/dashboards/union-admin/player-transfers/` | `union.transfers.view` |
| GET | `/api/dashboards/union-admin/player-transfers/<id>/` | `union.transfers.view` |
| POST | `.../<id>/record-offline-consent/` | `union.transfers.approve` |
| POST | `.../<id>/record-offline-decline/` | `union.transfers.approve` |
| POST | `.../<id>/request-changes/` | `union.transfers.approve` |
| POST | `.../<id>/reject/` | `union.transfers.approve` |
| POST | `.../<id>/approve/` | `union.transfers.approve` |

Union lists always exclude private `DRAFT` rows. Both source and destination
Club scopes are checked, as are every related competition identity and edition
scope. List responses use `{"count": 0, "results": []}` with repeated
`status`, fixed exact/date filters, search, and an allowlisted `ordering`.

Decision, request-changes, and rejection bodies contain only `workspace` and
non-empty `reason`. Verified offline consent additionally requires
`consent_method` and write-only `evidence_reference`; verified offline decline
requires `reason` and write-only `evidence_reference`.

Approval returns the stable normalized shape:

```json
{
  "transfer": {},
  "automatic_validation": null,
  "source_registration": {},
  "destination_registration": null,
  "return_registration": null,
  "destination_eligibilities": [],
  "return_eligibilities": [],
  "activation_scheduled": false,
  "idempotent_replay": false
}
```

`activation_scheduled=true` means the approved effective date is in the future
and no registration movement has occurred. `idempotent_replay=true` means the
existing authoritative result was returned without duplicate registration,
eligibility, notification, or irreversible audit records. Registration
summaries include IDs, state, type, Club/team/season, effective dates,
predecessor, and approval evidence. Eligibility summaries include IDs, state,
registration, Club/team/competition/season, dates, and source transfer/loan
return links.

There is no Union create/update route, start-review route, direct activation
route, direct loan-return route, or direct registration/eligibility movement
route.

## Privacy exclusions

Frontend code must never expect these fields from the maintained APIs:

- `activation_plan`
- `return_plan`
- permanent-player `identity_reference`
- offline `evidence_reference`
- audit-event metadata
- notification metadata or delivery internals
- scheduler/processor internal failure details

Date of birth is available only where contractually needed: Club registration
detail, Union registration review detail, and restricted Club registry search.
It is not exposed in transfer or eligibility responses. Write-only offline
evidence is validated but is neither echoed nor serialized.

## Scheduled processing

These are management commands, not HTTP endpoints:

```text
python manage.py process_scheduled_player_transfers [--as-of YYYY-MM-DD] [--limit N] [--dry-run]
python manage.py process_due_player_loan_returns [--as-of YYYY-MM-DD] [--limit N] [--dry-run]
```

Production operations should schedule each command daily, monitor its neutral
summary/failure output, and use `--dry-run` during deployment verification.
Do not expose either processor through the frontend or an API route.

## Route integrity

The `dashboards` and `teams` URL modules contain no duplicate route name.
Static action paths are distinct from numeric detail paths. Maintained and
legacy player/transfer IDs are resolved only within their own route families.
No Club route performs a Union decision, no Union route edits a Club draft,
and no HTTP route directly activates transfers, returns loans, or moves
authoritative registration/eligibility history.
