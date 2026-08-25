#!/usr/bin/env python3

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
TIMEOUT = 20

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
    # Rugby competitions. Rugby uses scoreboard for schedules.
    ("rugby", "268565", "British and Irish Lions Tour"),
    ("rugby", "164205", "Rugby World Cup"),
    ("rugby", "180659", "Six Nations"),
    ("rugby", "244293", "The Rugby Championship"),
    ("rugby", "271937", "European Rugby Champions Cup"),
    ("rugby", "272073", "European Rugby Challenge Cup"),
    ("rugby", "267979", "Gallagher Prem"),
    ("rugby", "270557", "United Rugby Championship"),
    ("rugby", "270559", "French Top 14"),
    ("rugby", "2009", "URBA Primera A"),
    ("rugby", "17567", "Nations Championship"),
    ("rugby", "242041", "Super Rugby Pacific"),
    ("rugby", "289271", "Super Rugby Aotearoa"),
    ("rugby", "289272", "Super Rugby AU"),
    ("rugby", "289277", "Super Rugby Trans-Tasman"),
    ("rugby", "289279", "URBA Top 14"),
    ("rugby", "270555", "Currie Cup"),
    ("rugby", "270563", "Mitre 10 Cup"),
    ("rugby", "236461", "Anglo-Welsh Cup"),
    ("rugby", "289274", "2020 Tri Nations"),
    ("rugby", "282", "Olympic Men's 7s"),
    ("rugby", "283", "Olympic Women's Rugby Sevens"),
    ("rugby", "289237", "Women's Rugby World Cup"),
    ("rugby", "289262", "Major League Rugby"),
    ("rugby", "289234", "International Test Match"),
    ("soccer", "club.friendly", "Club Friendly"),
]


def get_json(url, params=None):
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


def get_rugby_schedule(team_id, league_id, start_year=None, end_year=None):
    """Retrieve rugby events through ESPN's scoreboard endpoint.

    ESPN's rugby team schedule endpoint returns HTTP 500, while the
    competition scoreboard endpoint works. ESPN also rejects overly large
    date ranges, so query one calendar year at a time.
    """
    now = datetime.now(timezone.utc)

    start_year = start_year or now.year
    end_year = end_year or (now.year + 1)

    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/"
        f"rugby/{league_id}/scoreboard"
    )

    matched = []
    seen_ids = set()

    for year in range(start_year, end_year + 1):
        response = requests.get(
            url,
            params={"dates": f"{year:04d}0101-{year:04d}1231"},
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        for event in data.get("events", []):
            event_id = event.get("id")

            if event_id in seen_ids:
                continue

            participants = []

            for competition in event.get("competitions", []):
                for competitor in competition.get("competitors", []):
                    competitor_team = competitor.get("team", {})
                    competitor_id = competitor_team.get("id")

                    if competitor_id is not None:
                        participants.append(str(competitor_id))

            if str(team_id) in participants:
                matched.append(event)
                seen_ids.add(event_id)

    return {"events": matched}



def get_schedule(sport, league, team_id, season):
    """Retrieve the selected team's schedule.

    Soccer teams can appear in multiple configured ESPN leagues. For soccer,
    query each league's direct team schedule endpoint so --season is honored,
    then merge the returned events. Other sports use the selected league.
    """
    if sport == "soccer":
        schedules = []

        for route_sport, route_league, route_name in ESPN_ROUTES:
            if route_sport != "soccer":
                continue

            try:
                params = {"season": season} if season else {}
                url = (
                    f"{SITE_BASE}/sports/{route_sport}/{route_league}/"
                    f"teams/{team_id}/schedule"
                )
                schedule = get_json(url, params)
            except RuntimeError:
                continue

            if schedule.get("events"):
                schedules.append(schedule)

        return merge_schedules(*schedules)

    schedule_getters = {
        "rugby": get_rugby_schedule,
    }

    getter = schedule_getters.get(sport, get_full_schedule)

    if sport == "rugby":
        season_year = int(season) if season else None
        return getter(
            team_id,
            league,
            start_year=season_year,
            end_year=(season_year + 1) if season_year else None,
        )

    return getter(
        sport,
        league,
        team_id,
        season,
    )

def get_full_schedule(
    sport,
    league,
    team_id,
    season=None,
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

    For non-soccer sports, the normal team schedule endpoint is
    the appropriate full-season endpoint.
    """
    params = {}

    if season:
        params["season"] = season

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

        event.add(
            "summary",
            event_data.get("name", "ESPN Event"),
        )

        venue = get_venue(event_data)
        if venue:
            event.add("location", venue)

        description = [
            f"Sport: {sport}",
            f"League: {league}",
        ]

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
        "--season",
        metavar="YEAR",
        help="Season year, e.g. 2026.",
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


def print_season(season):
    if season:
        print(f"Season: {season}")


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
    return (
        args.ical
        or f"{safe_filename(team.get('displayName', 'schedule'))}.ics"
    )


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

    print_season(args.season)

    schedule = get_schedule(
        sport,
        league,
        team["id"],
        args.season,
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


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
