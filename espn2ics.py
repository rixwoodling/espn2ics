#!/usr/bin/env python3

"""ESPN team schedule to JSON/iCalendar.

v5 revised: NHL regular-season retrieval now discovers the current ESPN
season from the Core API calendar and requests the full schedule with
seasontype=2.
"""

import argparse
import re
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from icalendar import Calendar, Event

SITE_BASE = "https://site.api.espn.com/apis/site/v2"
WEB_BASE = "https://site.web.api.espn.com/apis/site/v2"
CORE_BASE = "https://sports.core.api.espn.com/v2"
TIMEOUT = 20
API_PINGS = 0

# Search routes. The user never specifies a sport.
ESPN_ROUTES = [
    ("football", "nfl", "NFL"),
    ("football", "college-football", "NCAA Football"),
    ("basketball", "nba", "NBA"),
    ("basketball", "wnba", "WNBA"),
    ("basketball", "mens-college-basketball", "NCAA Men's Basketball"),
    ("basketball", "womens-college-basketball", "NCAA Women's Basketball"),
    ("hockey", "nhl", "NHL"),
    ("hockey", "mens-college-hockey", "NCAA Men's Hockey"),
    ("hockey", "womens-college-hockey", "NCAA Women's Hockey"),
    ("baseball", "mlb", "MLB"),
    ("baseball", "college-baseball", "NCAA Baseball"),
    ("soccer", "eng.1", "English Premier League"),
    ("soccer", "esp.1", "La Liga"),
    ("soccer", "ger.1", "Bundesliga"),
    ("soccer", "ita.1", "Serie A"),
    ("soccer", "fra.1", "Ligue 1"),
    ("soccer", "ned.1", "Eredivisie"),
    ("soccer", "por.1", "Primeira Liga"),
    ("soccer", "sco.1", "Scottish Premiership"),
    ("soccer", "bel.1", "Belgian Pro League"),
    ("soccer", "tur.1", "Turkish Super Lig"),
    ("soccer", "usa.1", "MLS"),
    ("soccer", "usa.nwsl", "NWSL"),
    ("soccer", "mex.1", "Liga MX"),
    ("soccer", "uefa.champions", "UEFA Champions League"),
    ("soccer", "uefa.europa", "UEFA Europa League"),
    ("soccer", "uefa.europa.conf", "UEFA Conference League"),
    ("soccer", "club.friendly", "Club Friendly"),
]

def get_json(url, params=None):
    global API_PINGS
    API_PINGS += 1
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        raise RuntimeError(str(exc)) from exc
    except ValueError as exc:
        raise RuntimeError("ESPN returned invalid JSON") from exc

def normalize(value):
    value = str(value or "").lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    words = value.split()
    while words and words[-1] == "fc":
        words.pop()
    return " ".join(words)

def team_score(team, requested):
    """
    Score a team name conservatively.

    Exact/full-name matches are preferred. A weak partial match
    is allowed only when the requested name is a meaningful
    substring of the team's full display name.

    This prevents:
        "Portland Thorns"
    from matching:
        "Portland Timbers"

    merely because both contain "Portland".
    """
    requested = normalize(requested)

    if not requested:
        return 0

    requested_words = requested.split()

    fields = [
        team.get("displayName", ""),
        team.get("name", ""),
        team.get("shortDisplayName", ""),
        team.get("location", ""),
        team.get("nickname", ""),
        team.get("slug", ""),
        team.get("abbreviation", ""),
    ]

    best = 0

    for raw_field in fields:
        field = normalize(raw_field)

        if not field:
            continue

        field_words = field.split()

        # Exact full-field match.
        if field == requested:
            best = max(best, 100)
            continue

        # The requested name is the complete prefix/suffix
        # of the full display name.
        if (
            len(requested_words) >= 2
            and (
                field.startswith(requested + " ")
                or field.endswith(" " + requested)
            )
        ):
            best = max(best, 90)
            continue

        # Multi-word requested names may occur as a contiguous
        # phrase inside a longer display name.
        if len(requested_words) >= 2:
            if requested in field:
                best = max(best, 80)
            continue

        # For a one-word request such as "Oregon", allow the
        # word to match, because this is intentionally useful
        # for ambiguous searches.
        if len(requested_words) == 1:
            if requested in field_words:
                best = max(best, 70)

    return best


def get_teams(sport, league):
    url = f"{SITE_BASE}/sports/{sport}/{league}/teams"
    data = get_json(url, {"limit": 500})

    teams = []
    for sport_entry in data.get("sports", []):
        for league_entry in sport_entry.get("leagues", []):
            for item in league_entry.get("teams", []):
                team = item.get("team", item)
                if isinstance(team, dict) and team.get("id"):
                    teams.append(team)
    return teams


def find_team(team_name, sport_filter=None):
    """
    Search every configured ESPN route.

    Multiple competition entries for the same ESPN team ID are
    collapsed before ambiguity is checked.
    """
    by_team_id = {}

    for sport, league, league_name in ESPN_ROUTES:
        if sport_filter and sport != sport_filter:
            continue

        try:
            teams = get_teams(sport, league)
        except RuntimeError:
            continue

        for team in teams:
            score = team_score(team, team_name)
            if not score:
                continue

            team_id = str(team["id"])
            candidate = {
                "team": team,
                "sport": sport,
                "league": league,
                "league_name": league_name,
                "score": score,
            }

            old = by_team_id.get(team_id)
            if old is None or score > old["score"]:
                by_team_id[team_id] = candidate

    candidates = list(by_team_id.values())

    if not candidates:
        print(f'ERROR: Team not found: "{team_name}"', file=sys.stderr)
        sys.exit(1)

    best_score = max(x["score"] for x in candidates)
    candidates = [x for x in candidates if x["score"] == best_score]

    if len(candidates) > 1:
        print()
        print(f'Multiple teams matched "{team_name}":')
        print()
        for x in sorted(
            candidates,
            key=lambda c: c["team"].get("displayName", ""),
        ):
            print(
                f'  {x["team"]["id"]}: '
                f'{x["team"].get("displayName", x["team"].get("name", "?"))}'
            )
            print(f'      Sport: {x["sport"]}')
            print(f'      League: {x["league_name"]}')

        print("\nUse a more specific team name.", file=sys.stderr)
        sys.exit(1)

    return candidates[0]


def parse_datetime(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def event_key(event):
    event_id = event.get("id")
    if event_id:
        return str(event_id)

    return "|".join(
        [
            str(event.get("date", "")),
            str(event.get("name", "")),
        ]
    )

def extract_events(data):
    events = data.get("events", [])
    if isinstance(events, list):
        return events
    return []

def get_current_soccer_schedule(team_id):
    """Retrieve the current/upcoming soccer schedule.

    Use ESPN's cross-competition fixture schedule plus Club Friendly.
    This is the default mode: callers can filter the returned events to
    today and later without reconstructing the schedule from past scores.
    """
    schedules = []

    try:
        schedule = get_full_schedule(
            "soccer",
            "",
            team_id,
            None,
        )
        if schedule.get("events"):
            schedules.append(schedule)
    except RuntimeError:
        pass

    # Club Friendly is not reliably exposed by the cross-competition
    # "all" endpoint, so explicitly add it.
    try:
        url = (
            f"{SITE_BASE}/sports/soccer/club.friendly/"
            f"teams/{team_id}/schedule"
        )
        schedule = get_json(url)
        if schedule.get("events"):
            schedules.append(schedule)
    except RuntimeError:
        pass

    return filter_current_events(merge_schedules(*schedules))

def filter_current_events(schedule):
    """Keep only events occurring today or later."""
    today = datetime.now().astimezone().date()

    events = []
    for event in extract_events(schedule):
        dt = parse_datetime(event.get("date"))
        if dt is None:
            continue
        if dt.astimezone().date() >= today:
            events.append(event)

    return {"events": events}

def get_current_hockey_schedule(team_id):
    """Retrieve the current/upcoming NHL regular-season schedule.

    ESPN's NHL team schedule endpoint returns the full season when given
    both the ESPN season number and ``seasontype=2``.  The NHL season number
    is discovered from ESPN's own Core API calendar instead of being
    hard-coded or inferred from a September cutoff.
    """
    calendar_url = (
        f"{CORE_BASE}/sports/hockey/leagues/nhl/calendar/ondays"
    )

    calendar = get_json(
        calendar_url,
        {"lang": "en", "region": "us"},
    )

    season_ref = calendar.get("season", {}).get("$ref", "")
    match = re.search(r"/seasons/(\d+)(?:\?|$)", season_ref)

    if not match:
        raise RuntimeError(
            "ESPN NHL calendar did not provide a season number"
        )

    season = int(match.group(1))

    schedule = get_full_schedule(
        "hockey",
        "nhl",
        team_id,
        season=season,
        seasontype=2,
    )

    return filter_current_events(schedule)

def get_current_nba_schedule(team_id):
    """Retrieve the current/upcoming NBA schedule."""
    today = datetime.now().date()

    # ESPN labels NBA seasons by the year in which they end.
    season = today.year if today.month <= 6 else today.year + 1

    schedule = get_full_schedule(
        "basketball",
        "nba",
        team_id,
        season=season,
    )

    return filter_current_events(schedule)


def get_current_wnba_schedule(team_id):
    """Retrieve the current/upcoming WNBA schedule."""
    schedule = get_full_schedule(
        "basketball",
        "wnba",
        team_id,
    )
    return filter_current_events(schedule)

def get_current_nfl_schedule(team_id):
    """Retrieve the current/upcoming NFL schedule."""
    schedule = get_full_schedule(
        "football",
        "nfl",
        team_id,
    )
    return filter_current_events(schedule)

def get_current_ncaa_football_schedule(team_id):
    """Retrieve the current/upcoming NCAA football schedule."""
    schedule = get_full_schedule(
        "football",
        "college-football",
        team_id,
    )
    return filter_current_events(schedule)

def get_current_mlb_schedule(team_id):
    """Retrieve the current/upcoming MLB schedule."""
    schedule = get_full_schedule(
        "baseball",
        "mlb",
        team_id,
    )
    return filter_current_events(schedule)

def get_current_ncaa_baseball_schedule(team_id):
    """Retrieve the current/upcoming NCAA baseball schedule."""
    schedule = get_full_schedule(
        "baseball",
        "college-baseball",
        team_id,
    )
    return filter_current_events(schedule)

def get_current_nhl_schedule(team_id):
    """Retrieve the current/upcoming NHL regular-season schedule.

    ESPN's NHL season numbering and preseason/postseason behavior are
    different from most other sports. The current season is discovered
    from ESPN's Core calendar, then the regular-season type is requested
    explicitly.
    """
    core_base = "https://sports.core.api.espn.com/v2"

    calendar_url = (
        f"{core_base}/sports/hockey/leagues/nhl/calendar/ondays"
    )

    calendar = get_json(
        calendar_url,
        {"lang": "en", "region": "us"},
    )

    season_ref = calendar.get("season", {}).get("$ref", "")
    match = re.search(r"/seasons/(\d+)(?:\?|$)", season_ref)

    if not match:
        raise RuntimeError(
            "ESPN NHL calendar did not provide a season number"
        )

    season = int(match.group(1))

    schedule = get_full_schedule(
        "hockey",
        "nhl",
        team_id,
        season=season,
        seasontype=2,
    )

    return filter_current_events(schedule)

def get_current_college_hockey_schedule(team_id):
    """Retrieve the current/upcoming NCAA hockey schedule."""
    schedule = get_full_schedule(
        "hockey",
        "mens-college-hockey",
        team_id,
    )
    return filter_current_events(schedule)

# Explicit league handlers keep sport-specific behavior isolated.
# Adding or changing one league should not require editing another.
SCHEDULE_HANDLERS = {
    ("soccer", "eng.1"): get_current_soccer_schedule,
    ("soccer", "esp.1"): get_current_soccer_schedule,
    ("soccer", "ger.1"): get_current_soccer_schedule,
    ("soccer", "ita.1"): get_current_soccer_schedule,
    ("soccer", "fra.1"): get_current_soccer_schedule,
    ("soccer", "ned.1"): get_current_soccer_schedule,
    ("soccer", "por.1"): get_current_soccer_schedule,
    ("soccer", "sco.1"): get_current_soccer_schedule,
    ("soccer", "bel.1"): get_current_soccer_schedule,
    ("soccer", "tur.1"): get_current_soccer_schedule,
    ("soccer", "usa.1"): get_current_soccer_schedule,
    ("soccer", "usa.nwsl"): get_current_soccer_schedule,
    ("soccer", "mex.1"): get_current_soccer_schedule,
    ("soccer", "uefa.champions"): get_current_soccer_schedule,
    ("soccer", "uefa.europa"): get_current_soccer_schedule,
    ("soccer", "uefa.europa.conf"): get_current_soccer_schedule,
    ("soccer", "club.friendly"): get_current_soccer_schedule,

    ("basketball", "nba"): get_current_nba_schedule,
    ("basketball", "wnba"): get_current_wnba_schedule,

    ("football", "nfl"): get_current_nfl_schedule,
    ("football", "college-football"): get_current_ncaa_football_schedule,

    ("hockey", "nhl"): get_current_nhl_schedule,
    ("hockey", "mens-college-hockey"): get_current_college_hockey_schedule,

    ("baseball", "mlb"): get_current_mlb_schedule,
    ("baseball", "college-baseball"): get_current_ncaa_baseball_schedule,
}

def get_generic_current_schedule(sport, league, team_id):
    """Generic fallback for routes without a dedicated handler."""
    schedule = get_full_schedule(
        sport,
        league,
        team_id,
    )

    return filter_current_events(schedule)


def get_schedule(sport, league, team_id):
    """Route a team to an isolated league-specific schedule handler."""
    handler = SCHEDULE_HANDLERS.get((sport, league))

    if handler:
        return handler(team_id)

    return get_generic_current_schedule(
        sport,
        league,
        team_id,
    )

def get_schedule(sport, league, team_id):
    """Retrieve today's and future events without scanning historical scores."""
    if sport == "soccer":
        return get_current_soccer_schedule(team_id)

    if sport == "basketball" and league == "nba":
        return get_current_nba_schedule(team_id)

    if sport == "hockey" and league == "nhl":
        return get_current_hockey_schedule(team_id)

    schedule = get_full_schedule(
        sport,
        league,
        team_id,
        None,
    )
    if sport in {"football", "basketball", "hockey", "baseball"}:
        return filter_current_events(schedule)

    return schedule

def get_full_schedule(
    sport,
    league,
    team_id,
    season=None,
    seasontype=None,
):
    """
    Retrieve the full team schedule.

    ESPN's soccer endpoint changed behavior. The normal
    site.api schedule can return only a narrow/current window.
    For soccer, ESPN's web API exposes the team's cross-
    competition fixture schedule through:

        /sports/soccer/all/teams/{id}/schedule?fixture=true

    We try the full/cross-competition endpoint first for soccer,
    then fall back to the normal team schedule endpoint.

    League-specific handlers decide whether a season or season type
    is required. This function only handles the ESPN endpoint call.

    ``season`` and ``seasontype`` are passed through when supplied.
    NHL uses ``seasontype=2`` for the regular season.
    """
    params = {}

    if season is not None:
        params["season"] = season

    if seasontype is not None:
        params["seasontype"] = seasontype

    if sport == "soccer":
        # This is the endpoint used by ESPN's soccer fixtures page.
        # "all" is important: it includes the team's competitions,
        # not just the league route used to discover the team.
        url = (
            f"{WEB_BASE}/sports/soccer/all/"
            f"teams/{team_id}/schedule"
        )
        fixture_params = dict(params)
        fixture_params["fixture"] = "true"

        try:
            data = get_json(
                url,
                fixture_params,
            )
            events = extract_events(data)

            if events:
                return data
        except RuntimeError:
            pass

        # Also try the same endpoint without fixture=true.
        # This can expose completed fixtures that the fixture
        # view omits.
        try:
            data = get_json(
                url,
                params,
            )
            events = extract_events(data)

            if events:
                return data
        except RuntimeError:
            pass

    # Standard ESPN schedule endpoint.
    url = (
        f"{SITE_BASE}/sports/{sport}/{league}/"
        f"teams/{team_id}/schedule"
    )
    return get_json(url, params)

def merge_schedules(*schedules):
    """
    Merge event lists and remove duplicate event IDs.
    """
    result = []
    seen = set()

    for schedule in schedules:
        for event in extract_events(schedule):
            key = event_key(event)
            if key in seen:
                continue
            seen.add(key)
            result.append(event)

    return {"events": result}

def get_broadcasts(event):
    """Return current U.S. broadcast names from ESPN event data."""
    broadcasts = []

    for competition in event.get("competitions", []):
        for broadcast in competition.get("broadcasts", []):
            if broadcast.get("region") != "us":
                continue

            media = broadcast.get("media", {})
            name = media.get("shortName") or media.get("name")
            if not name:
                continue

            broadcast_type = broadcast.get("type", {})
            kind = (
                broadcast_type.get("shortName")
                or broadcast_type.get("name")
                or ""
            )
            item = {
                "name": name,
                "type": kind,
                "region": "us",
            }
            if item not in broadcasts:
                broadcasts.append(item)

    return broadcasts

def get_broadcast_names(event):
    """Return unique U.S. broadcast names for display."""
    return list(dict.fromkeys(
        broadcast["name"] for broadcast in get_broadcasts(event)
    ))

def get_venue(event):
    competitions = event.get("competitions", [])
    if not competitions:
        return ""

    venue = competitions[0].get("venue", {})
    return venue.get("fullName", "")

def format_event(event):
    dt = parse_datetime(event.get("date"))

    if dt:
        local = dt.astimezone()
        date = local.strftime("%Y-%m-%d")
        time = local.strftime("%H:%M")
    else:
        date = "Unknown"
        time = ""

    text = f"{date} {time}  {event.get('name', 'Unknown event')}"

    broadcast_names = get_broadcast_names(event)
    if broadcast_names:
        text += f"  [TV: {', '.join(broadcast_names)}]"

    venue = get_venue(event)
    if venue:
        text += f"  @ {venue}"

    return text

def safe_filename(name):
    return (
        re.sub(r"[^\w.-]+", "_", name).strip("_")
        or "schedule"
    )

def create_ical(
    team,
    sport,
    league,
    schedule,
    output_path,
):
    calendar = Calendar()

    team_name = (
        team.get("displayName")
        or team.get("name")
        or "ESPN Schedule"
    )
    calendar.add("prodid", "-//ESPN Schedule//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("X-WR-CALNAME", team_name)
    calendar.add(
        "X-WR-CALDESC",
        f"{team_name} schedule from ESPN",
    )
    for event_data in schedule.get("events", []):
        dt = parse_datetime(event_data.get("date"))
        if dt is None:
            continue

        event = Event()

        event_id = event_data.get("id")
        if event_id:
            event.add(
                "uid",
                f"espn-{event_id}@espn.py",
            )
        event.add("dtstart", dt)

        summary = event_data.get("name", "ESPN Event")

        broadcast_names = get_broadcast_names(event_data)
        if broadcast_names:
            summary += f" [TV: {', '.join(broadcast_names)}]"

        event.add("summary", summary)

        venue = get_venue(event_data)
        if venue:
            event.add("location", venue)

        description = [
            f"Sport: {sport}",
            f"League: {league}",
        ]
        broadcast_names = get_broadcast_names(event_data)
        if broadcast_names:
            description.append(
                f"TV: {', '.join(broadcast_names)}"
            )
        short_name = event_data.get("shortName")
        if short_name:
            description.insert(
                0,
                f"Game: {short_name}",
            )
        event.add(
            "description",
            "\n".join(description),
        )
        calendar.add_component(event)

    with Path(output_path).open("wb") as f:
        f.write(calendar.to_ical())

def parse_args():
    sports = sorted({sport for sport, _, _ in ESPN_ROUTES})

    sport_lines = [
        "  " + ", ".join(sports)
    ]
    parser = argparse.ArgumentParser(
        description="Find a team and retrieve its ESPN schedule.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Sports currently searched:\n"
            + "\n".join(sport_lines)
            + "\n\nExamples:\n"
            '  %(prog)s --team "Liverpool"\n'
            '  %(prog)s --team "Oregon Ducks" --sport football\n'
            '  %(prog)s --team "Portland Fire" --sport basketball\n'
            '  %(prog)s --team "Liverpool" --ical\n'
        ),
    )
    parser.add_argument(
        "--team",
        required=True,
        metavar="TEAM",
        help="Team name to search for.",
    )
    parser.add_argument(
        "--sport",
        choices=sports,
        metavar="SPORT",
        help="Limit the search to one sport.",
    )
    parser.add_argument(
        "--ical",
        nargs="?",
        const="",
        metavar="FILE",
        help="Create an iCalendar file; default filename is TEAM.ics.",
    )
    parser.add_argument(
        "--json",
        nargs="?",
        const="",
        default=None,
        metavar="FILE",
        help="Create a JSON file in the json/ directory; default filename is TEAM.json.",
    )
    return parser.parse_args()

def print_team_info(result):
    team = result["team"]

    print(
        f"Team: {team.get('displayName', team.get('name', '?'))}"
    )
    print(f"Team ID: {team['id']}")
    print(f"Sport: {result['sport']}")
    print(f"League: {result['league_name']}")

def sort_events(schedule):
    return sorted(
        extract_events(schedule),
        key=lambda event: (
            parse_datetime(event.get("date"))
            or datetime.max.replace(tzinfo=timezone.utc)
        ),
    )

def print_schedule(events):
    print()
    print("Schedule:")
    print("-" * 80)

    for event in events:
        print(format_event(event))

    print()
    print(f"Found {len(events)} event(s).")


def build_ical_output(args, team):
    ical_dir = Path("ical")
    ical_dir.mkdir(parents=True, exist_ok=True)

    filename = (
        args.ical
        or f"{safe_filename(team.get('displayName', 'schedule'))}.ics"
    )
    return str(ical_dir / Path(filename).name)

def create_ical_if_requested(
    args,
    team,
    sport,
    league,
    schedule,
):
    if args.ical is None:
        return

    output_path = build_ical_output(
        args,
        team,
    )
    create_ical(
        team,
        sport,
        league,
        schedule,
        output_path,
    )
    print(f"iCalendar: {output_path}")

def handle_schedule_result(events, args, team, sport, league, schedule):
    if not events:
        print("No events found.")
        return

    print_schedule(events)

    create_ical_if_requested(
        args,
        team,
        sport,
        league,
        schedule,
    )

def no_events_check(events):
    if not events:
        print("No events found.")
        sys.exit(0)

def create_json_if_requested(args, team, sport, league, schedule):
    if args.json is None:
        return

    json_dir = Path("json")
    json_dir.mkdir(parents=True, exist_ok=True)

    team_name = team.get("displayName") or team.get("name", "team")
    filename = args.json or f"{team_name.replace(' ', '_')}.json"
    filename = Path(filename).name
    output_path = json_dir / filename

    data = {
        "team": {
            "id": str(team.get("id", "")),
            "name": team.get("displayName") or team.get("name", ""),
        },
        "sport": sport,
        "league": league,
        "events": schedule.get("events", []),
    }
    for event in data["events"]:
        broadcasts = get_broadcasts(event)
        if broadcasts:
            event["broadcasts"] = broadcasts

    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Created JSON: {output_path}")

def main():
    args = parse_args()

    print(f"Finding team: {args.team}")

    result = find_team(
        args.team,
        args.sport,
    )
    print_team_info(result)

    team = result["team"]
    sport = result["sport"]
    league = result["league"]

    schedule = get_schedule(
        sport,
        league,
        team["id"],
    )

    events = sort_events(schedule)

    no_events_check(events)

    print_schedule(events)

    create_ical_if_requested(
        args,
        team,
        sport,
        league,
        schedule,
    )
    create_json_if_requested(
        args,
        team,
        sport,
        league,
        schedule,
    )
    print(f"API requests: {API_PINGS}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


