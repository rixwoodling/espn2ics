# ESPN Schedule to iCalendar

A small Python command-line tool for finding sports teams through ESPN and retrieving their schedules, with optional iCalendar output.

The goal is simple: give it a team name, let ESPN determine the team and competition, and get a usable schedule without having to manually know ESPN's internal league IDs.

## `espn11.2.py`

Searches the currently supported ESPN sports and retrieves a team's schedule.

```bash
python3 espn11.2.py --team "Liverpool"
```

Example:

```text
Finding team: Liverpool
Team: Liverpool
Team ID: 364
Sport: soccer
League: English Premier League

Schedule:
--------------------------------------------------------------------------------
2026-08-29 04:30  Nottingham Forest at Liverpool  @ Anfield
...
Found 37 event(s).
```

### Sport selection

`--sport` is optional.

Use it when a team name is shared by multiple sports:

```bash
python3 espn11.2.py --team "Oregon Ducks" --sport football
python3 espn11.2.py --team "Oregon Ducks" --sport baseball
```

Currently supported sports:

```text
baseball
basketball
football
hockey
rugby
soccer
```

Without `--sport`, the script searches all configured leagues and uses the best team match. If different ESPN team IDs match, it reports the ambiguity instead of guessing.

## iCalendar

Create an `.ics` file:

```bash
python3 espn11.2.py --team "Liverpool" --ical
```

Specify the filename:

```bash
python3 espn11.2.py --team "Liverpool" --ical Liverpool.ics
```

This produces a standard iCalendar file containing the schedule, venue, sport, and league information.

## Seasons

A season can be specified explicitly:

```bash
python3 espn11.2.py     --team "Portland Pilots"     --sport basketball     --season 2026
```

ESPN's season numbering is competition-dependent. For example, `season=2026` can return the 2025-26 NCAA men's basketball schedule.

When no season is supplied, the script uses ESPN's current schedule data. If ESPN has the current season but has not populated any events yet, the script reports no events rather than silently substituting an older season.

## Rugby

Rugby is handled differently from the other supported sports because ESPN's rugby team schedule endpoint returns HTTP 500.

For rugby, the script instead queries the competition scoreboard endpoint over calendar-year ranges and filters the results to the selected team.

Example:

```bash
python3 espn11.2.py --team "New Zealand" --sport rugby
```

This supports ESPN rugby competitions including:

```text
British and Irish Lions Tour
Rugby World Cup
Six Nations
The Rugby Championship
European Rugby Champions Cup
European Rugby Challenge Cup
Gallagher Prem
United Rugby Championship
French Top 14
Super Rugby Pacific
Major League Rugby
International Test Match
...
```

## Installation

Create a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the dependencies:

```bash
python3 -m pip install requests icalendar
```

Then run:

```bash
python3 espn11.2.py --help
```

## Pipeline

The command-line workflow is intentionally kept as a simple pipeline:

```text
parse_args()
    ↓
find_team()
    ↓
print_team_info()
    ↓
get_schedule()
    ↓
sort_events()
    ↓
print_schedule()
    ↓
create_ical_if_requested()
```

Sport-specific API differences are kept inside the schedule retrieval layer rather than spreading ESPN-specific conditionals through `main()`.

## ESPN API notes

This project uses ESPN's publicly accessible site/core API endpoints rather than an official paid developer API.

ESPN's endpoints are not guaranteed to remain stable. Some competitions use different endpoints or expose incomplete current-season data. The script therefore treats team discovery and schedule retrieval separately and uses competition-specific handling where necessary.

## Examples

```bash
# EPL
python3 espn11.2.py --team "Liverpool"

# NCAA football
python3 espn11.2.py --team "Oregon Ducks" --sport football

# NCAA baseball
python3 espn11.2.py --team "Oregon Ducks" --sport baseball

# NWSL
python3 espn11.2.py --team "Portland Thorns" --sport soccer

# WNBA
python3 espn11.2.py --team "Portland Fire" --sport basketball

# NHL
python3 espn11.2.py --team "Boston Bruins" --sport hockey

# Rugby
python3 espn11.2.py --team "New Zealand" --sport rugby

# iCalendar
python3 espn11.2.py --team "Liverpool" --ical
```
