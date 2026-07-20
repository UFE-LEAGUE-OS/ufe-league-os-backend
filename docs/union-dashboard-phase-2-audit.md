# Union Dashboard Phase 2: Baseline Audit

Date: 2026-07-20

## Existing backend capabilities to retain

- `dashboards` already owns the Union, League, Competition, Season,
  `LeagueClubMembership`, Union workspace, national-team, registration, match
  official, and fixture-appointment records.
- The workspace membership model already carries an exact workspace role,
  active state, extra permissions, and a sorted effective-permission contract.
- `union_management_views.py` already exposes workspace-scoped CRUD for clubs,
  leagues, seasons, competitions, league memberships, national teams,
  registrations, officials, appointments, and promotion/relegation actions.
- `teams` already owns `Team`, `PlayerRegistration`, and `PlayerTransfer`.
- Existing dashboard tests cover scope isolation for Union workspaces, club
  membership, national teams, registration review, official readiness, and
  official appointments.
- `accounts` already provides user accounts, `RoleApproval`, `ClubAdminScope`,
  notification records, payment history, and an immutable-style audit log.
- `sponsorships` already owns Sponsor accounts, members, agreements, payments,
  workflow events, and governance configuration.

## Existing frontend capabilities to retain

- The Union dashboard is entitlement-aware: it intersects `/me` dashboard
  entitlements with active workspace memberships before a workspace can be
  selected.
- The dashboard already has URL-safe protected routing, a desktop/mobile
  workspace shell, workspace switching, permission-filtered tabs, and no
  Fan-dashboard navigation in the Union workspace.
- Existing panels provide management workflows for competitions and clubs,
  national teams and registrations, referees and appointments, league-admin
  scopes, finance overview, ticketing, users, and operational status views.
- `dashboardAccess.ts` validates the versioned entitlement contract before a
  protected route is authorised.

## Gaps requiring Phase 2 work

1. **Competition lifecycle.** Competition currently combines permanent
   identity and season-facing data. It needs an explicit competition identity
   and season-edition lifecycle, with activation and archival history that is
   safe for historical fixtures, standings, registrations, finance, and
   reports.
2. **Governance.** Approval decisions and audit events exist in isolated
   forms, but Union actions do not have a shared approval/audit service or a
   filtered Union audit API.
3. **Registrations and transfers.** Current registration applications and
   player records are useful inputs, but approval, rejection, suspension,
   documents, transfer approval, and immutable registration history need a
   single, transactional Union workflow.
4. **Operational records.** Promotion/relegation needs a first-class decision
   record. Official availability, reports, documents, and allowances are not
   yet backed by their required operational models and APIs.
5. **Finance, communications, and Union sponsorship.** Existing generic
   payment, notification, and sponsorship models are reusable, but Union
   scoped invoices, payments, expenses, payouts, broadcasts, documents,
   sponsor placement, and reporting endpoints are incomplete.
6. **User administration.** Workspace membership endpoints exist; invite,
   deactivate, role-change approval, and detailed audit trails must be made
   explicit and ownership-safe.
7. **Frontend composition.** Existing panels should be retained and refactored
   into URL-backed feature tabs. Empty placeholder tabs must be replaced only
   when corresponding authenticated API data exists; unavailable operations
   should use a clear capability state rather than invented metrics.

## Proposed extension boundaries

- Keep `dashboards` as the Union operational boundary. Add only Union-owned
  models there, with foreign keys to `teams`, `accounts`, and `sponsorships`
  rather than duplicating those domains.
- Reuse the existing Union workspace permission helper for every endpoint.
  Mutations require an explicit operation permission and write an audit event.
- Keep permanent competition identity separate from season editions; retain
  `Competition` compatibility through a data migration and compatibility
  serializers until consumers have migrated.
- Make approval transitions transactional and idempotent. Existing records are
  never deleted or reassigned by a migration.
- Preserve the versioned dashboard-entitlement contract and its scoped route
  protection. Phase 2 may add tabs and workspace data, but must not fall back
  to role-only or Fan routing.

## Migration approach

1. Add nullable, additive models and foreign keys first.
2. Backfill editions and audit records in deterministic batches; preserve
   original IDs and timestamps where possible.
3. Validate counts and relationships before adding constraints or making new
   fields required.
4. Release read compatibility, then write compatibility, then remove legacy
   paths only in a later, separately reviewed migration.

## Suggested implementation sequence

1. Establish shared Union scope, audit, and approval services with tests.
2. Add competition identity/season-edition and historical-safe lifecycle
   support.
3. Complete club, player registration, transfer, and promotion workflows.
4. Add officials, national-team, finance, communications, sponsor, user, and
   reporting APIs in independently testable slices.
5. Replace matching frontend placeholder tabs with service-backed panels and
   URL-backed workspace state.
6. Add safe idempotent demo seed data, API documentation, and end-to-end
   regression coverage.
