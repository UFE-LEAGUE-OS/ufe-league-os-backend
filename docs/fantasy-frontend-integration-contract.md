# Fantasy League Frontend Integration Contract

## Purpose

This document defines the frontend integration contract for the League OS Fantasy League module.

It maps the approved fantasy frontend screens to backend API endpoints, expected request bodies, authentication requirements, and response usage.

## Base API Path

`/api/fantasy/`

## Authentication

Public browse endpoints may be used without login.

Most fan fantasy actions require an authenticated user.

Fantasy admin endpoints require one of the fantasy management roles:

* LEAGUE_ADMIN
* UNION_ADMIN
* SUPER_ADMIN
* REFEREE / MATCH_OFFICIAL for score entry only

Score approval and rejection require:

* LEAGUE_ADMIN
* UNION_ADMIN
* SUPER_ADMIN

---

## 1. Fantasy Hub & Competition Discovery

### Screen Purpose

Allows fans to discover active fantasy competitions.

### Endpoint

`GET /api/fantasy/competitions/`

### Query Parameters

* `sport=RUGBY`
* `status=OPEN`

### Example

`GET /api/fantasy/competitions/?sport=RUGBY&status=OPEN`

### Frontend Uses Response For

* Competition cards
* Sport label
* Season
* Budget
* Squad size
* Lineup size
* Rules summary
* Competition status

---

## 2. Fantasy Competition Detail

### Screen Purpose

Shows one fantasy competition with gameweeks and available leagues.

### Endpoint

`GET /api/fantasy/competitions/{competition_id}/`

### Example

`GET /api/fantasy/competitions/1/`

### Frontend Uses Response For

* Competition header
* Rules summary
* Gameweek list
* Available leagues
* CTA buttons:

  * Create Team
  * View Player Market
  * Join League

---

## 3. Competition Gameweeks

### Screen Purpose

Used by competition detail and lineup screens to show gameweeks.

### Endpoint

`GET /api/fantasy/competitions/{competition_id}/gameweeks/`

### Query Parameters

* `status=OPEN`
* `limit=20`
* `offset=0`

### Example

`GET /api/fantasy/competitions/1/gameweeks/?status=OPEN&limit=20&offset=0`

### Frontend Uses Response For

* Gameweek cards
* Lock status
* Open / locked / scoring / completed status
* Lineup availability

---

## 4. Player Market

### Screen Purpose

Allows fans to browse fantasy players before creating or editing a squad.

### Endpoint

`GET /api/fantasy/competitions/{competition_id}/players/`

### Query Parameters

* `search=Ian`
* `club=1`
* `position=BACK`
* `available=true`

### Example

`GET /api/fantasy/competitions/1/players/?available=true&position=BACK`

### Frontend Uses Response For

* Player list
* Position filters
* Club filters
* Price display
* Availability status
* Search results

---

## 5. Create Team / Squad Builder

### Create Fantasy Team

`POST /api/fantasy/teams/`

### Request Body

```json
{
  "fantasy_competition_id": 1,
  "name": "Kobs Warriors Fantasy XV"
}
```

### Response Usage

The frontend should save the returned team ID and then send the squad selection.

---

## 6. Review & Confirm Squad

### Endpoint

`POST /api/fantasy/teams/{team_id}/squad/`

### Request Body

```json
{
  "player_ids": [1, 2, 3, 4, 5]
}
```

### Backend Validates

* Exact squad size
* Budget limit
* Player availability
* No duplicate players
* Max players per club
* Players belong to the same competition

### Frontend Uses Response For

* Confirmed squad view
* Budget used
* Budget remaining
* Squad validation errors

---

## 7. My Fantasy Team Dashboard

### List My Teams

`GET /api/fantasy/teams/me/`

### Get One Team

`GET /api/fantasy/teams/{team_id}/`

### Frontend Uses Response For

* My fantasy teams
* Team name
* Total points
* Current rank
* Active squad
* Budget remaining

---

## 8. Gameweek Lineup Centre

### Submit Lineup

`POST /api/fantasy/teams/{team_id}/lineups/`

### Request Body

```json
{
  "gameweek_id": 1,
  "player_ids": [1, 2, 3],
  "captain_id": 1,
  "vice_captain_id": 2
}
```

### Backend Validates

* Gameweek belongs to the team competition
* Gameweek is not locked
* Lineup size is correct
* Players are in the active squad
* Captain is in lineup
* Vice captain is in lineup
* Captain and vice captain are not the same player

### List My Lineups

`GET /api/fantasy/lineups/me/`

---

## 9. Live Points / Gameweek Results / History

### Team History

`GET /api/fantasy/teams/{team_id}/history/`

### Gameweek Leaderboard

`GET /api/fantasy/gameweeks/{gameweek_id}/leaderboard/`

### Frontend Uses Response For

* Previous gameweek results
* Lineup history
* Team points
* Gameweek rank
* Player points breakdown

---

## 10. Fantasy Leagues & Leaderboards

### Create League

`POST /api/fantasy/leagues/`

### Request Body

```json
{
  "fantasy_competition_id": 1,
  "name": "KOBS Fans Mini League",
  "league_type": "PRIVATE"
}
```

### Available Leagues

`GET /api/fantasy/leagues/available/`

### Query Parameters

* `competition=1`
* `league_type=PUBLIC`
* `limit=20`
* `offset=0`

### Join Private League

`POST /api/fantasy/leagues/join/`

### Request Body

```json
{
  "fantasy_team_id": 1,
  "join_code": "ABCD1234"
}
```

### My Fantasy Leagues

`GET /api/fantasy/leagues/my/`

### League Detail

`GET /api/fantasy/leagues/{league_id}/`

### League Leaderboard

`GET /api/fantasy/leagues/{league_id}/leaderboard/`

### Gameweek League Leaderboard

`GET /api/fantasy/leagues/{league_id}/leaderboard/?gameweek_id=1`

### Privacy Rule

Public leagues can be viewed by anyone.

Private leagues can only be viewed by:

* The league creator
* A user who joined the league with one of their fantasy teams

---

## 11. Fantasy Admin Dashboard

### Endpoint

`GET /api/fantasy/admin/dashboard/`

### Query Parameters

* `competition=1`

### Frontend Uses Response For

Admin summary cards:

* Competitions count
* Open competitions count
* Gameweeks count
* Open gameweeks count
* Locked gameweeks count
* Completed gameweeks count
* Players count
* Available players count
* Teams count
* Leagues count
* Draft scores count
* Submitted scores count
* Approved scores count
* Rejected scores count

---

## 12. Fantasy Competition Setup

### List Competitions

`GET /api/fantasy/admin/competitions/`

### Query Parameters

* `sport=RUGBY`
* `status=OPEN`
* `search=Nile`
* `limit=20`
* `offset=0`

### Create Competition

`POST /api/fantasy/admin/competitions/`

### Update Competition

`PATCH /api/fantasy/admin/competitions/{competition_id}/`

### Example Update Body

```json
{
  "name": "Nile Special Rugby Fantasy 2026",
  "status": "OPEN",
  "budget": "100.00",
  "squad_size": 15,
  "lineup_size": 15,
  "max_players_per_club": 4,
  "captain_multiplier": "2.00",
  "min_player_price": "3.00",
  "max_player_price": "15.00",
  "default_player_price": "7.50",
  "rules_summary": "Pick a squad within budget before gameweek lock."
}
```

---

## 13. Gameweek Setup

### List Gameweeks

`GET /api/fantasy/admin/gameweeks/`

### Query Parameters

* `competition=1`
* `status=OPEN`
* `limit=20`
* `offset=0`

### Create Gameweek

`POST /api/fantasy/admin/gameweeks/`

### Update Gameweek

`PATCH /api/fantasy/admin/gameweeks/{gameweek_id}/`

### Example Update Body

```json
{
  "name": "Gameweek 1",
  "number": 1,
  "matches": [1, 2],
  "status": "OPEN"
}
```

---

## 14. Player Pricing

### List Admin Players

`GET /api/fantasy/admin/players/`

### Query Parameters

* `competition=1`
* `club=1`
* `position=BACK`
* `available=true`
* `search=Ian`
* `limit=20`
* `offset=0`

### Create Player

`POST /api/fantasy/admin/players/`

### Update Player

`PATCH /api/fantasy/admin/players/{player_id}/`

### Example Update Body

```json
{
  "display_name": "Ian Munyani",
  "position": "BACK",
  "previous_stats": {
    "appearances": 15,
    "tries": 7,
    "try_assists": 5,
    "tackles": 80,
    "metres_carried": 500,
    "clean_breaks": 12,
    "player_of_match": 3
  },
  "is_available": true,
  "availability_note": ""
}
```

### Manual Price Update

`PATCH /api/fantasy/admin/players/{player_id}/price/`

### Request Body

```json
{
  "final_price": "10.50",
  "price_override_reason": "Manual adjustment after admin review."
}
```

### Recalculate Price

`POST /api/fantasy/admin/players/{player_id}/recalculate-price/`

---

## 15. Score & Gameweek Operations

### List / Create Player Scores For Gameweek

`GET /api/fantasy/admin/gameweeks/{gameweek_id}/player-scores/`

`POST /api/fantasy/admin/gameweeks/{gameweek_id}/player-scores/`

### Query Parameters For GET

* `status=SUBMITTED`
* `limit=20`
* `offset=0`

### Create / Update Score Body

```json
{
  "fantasy_player_id": 1,
  "match_id": 1,
  "points": "8.00",
  "breakdown": {
    "appearance": 2,
    "try": 5,
    "assist": 1
  },
  "status": "SUBMITTED"
}
```

### Score Detail

`GET /api/fantasy/admin/player-scores/{score_id}/`

### Update Score

`PATCH /api/fantasy/admin/player-scores/{score_id}/`

### Approve Score

`POST /api/fantasy/admin/player-scores/{score_id}/approve/`

### Reject Score

`POST /api/fantasy/admin/player-scores/{score_id}/reject/`

### Calculate Gameweek Scores

`POST /api/fantasy/admin/gameweeks/{gameweek_id}/calculate/`

### Close Gameweek

`POST /api/fantasy/admin/gameweeks/{gameweek_id}/close/`

---

## Frontend Error Handling Guide

### 400 Bad Request

Used for validation errors.

Examples:

* Squad size is wrong
* Budget exceeded
* Player unavailable
* Lineup locked
* Invalid captain
* Invalid price range

### 401 Unauthorized

Used when the user is not logged in but the endpoint requires authentication.

### 403 Forbidden

Used when the user is logged in but does not have permission.

Examples:

* Fan accessing admin endpoint
* Referee attempting score approval or rejection
* User trying to view a private league they have not joined

### 404 Not Found

Used when the requested competition, team, league, gameweek, player, or score does not exist.

---

## Recommended Frontend Screen Mapping

| Screen                              | Primary Endpoint                                          |
| ----------------------------------- | --------------------------------------------------------- |
| Fantasy Hub & Competition Discovery | GET /api/fantasy/competitions/                            |
| Fantasy Competition Detail          | GET /api/fantasy/competitions/{id}/                       |
| Create Team / Squad Builder         | POST /api/fantasy/teams/                                  |
| Player Market                       | GET /api/fantasy/competitions/{id}/players/               |
| Review & Confirm Squad              | POST /api/fantasy/teams/{id}/squad/                       |
| My Fantasy Team Dashboard           | GET /api/fantasy/teams/me/                                |
| Gameweek Lineup Centre              | POST /api/fantasy/teams/{id}/lineups/                     |
| Live Points / History               | GET /api/fantasy/teams/{id}/history/                      |
| Fantasy Leagues & Leaderboards      | GET /api/fantasy/leagues/available/                       |
| Fantasy Admin Dashboard             | GET /api/fantasy/admin/dashboard/                         |
| Fantasy Competition Setup           | GET/PATCH /api/fantasy/admin/competitions/                |
| Gameweek Setup                      | GET/PATCH /api/fantasy/admin/gameweeks/                   |
| Player Pricing                      | GET/PATCH /api/fantasy/admin/players/                     |
| Score & Gameweek Operations         | GET/POST /api/fantasy/admin/gameweeks/{id}/player-scores/ |

---

## Frontend Notes

* Use `limit` and `offset` for paginated endpoints.
* Store the authenticated user's team ID after team creation.
* Do not show private league join codes publicly.
* Only show admin routes to permitted roles.
* Disable lineup editing after gameweek lock.
* Show score approval/rejection actions only to League Admin, Union Admin, or Super Admin.
* Show score entry actions to fantasy managers and match officials.
