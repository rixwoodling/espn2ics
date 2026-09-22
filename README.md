# ESPN Schedule to iCalendar

A small Python command-line tool for finding sports teams through ESPN and retrieving their **current and upcoming schedules**, with optional iCalendar and JSON output.

## `espn2ics.py`

The script searches the supported ESPN sports and retrieves events from **today forward**. It does not require a season argument and does not scan historical scoreboard dates to reconstruct a schedule.

The goal is simple: give it a team name, let ESPN determine the team and competition, and get a usable current/upcoming schedule without having to manually know ESPN's internal league IDs.

### Basic usage

```bash
python3 espn2ics.py --team "Liverpool"
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
API requests: 8
```

The schedule is filtered to **today and future events**. Completed events are not included.

## Sport selection

`--sport` is optional.

Use it when a team name is shared by multiple sports:

```bash
python3 espn2ics.py --team "Oregon Ducks" --sport football
python3 espn2ics.py --team "Oregon Ducks" --sport baseball
```

Currently supported sports:

```text
baseball
basketball
football
hockey
soccer
```

Rugby is **not supported**.

Without `--sport`, the script searches all configured leagues and uses the best team match. If different ESPN team IDs match, it reports the ambiguity instead of guessing.

## API request count

The script reports the number of ESPN API requests made during each run:

```text
Found 37 event(s).
API requests: 8
```

This makes it possible to measure and optimize the schedule lookup rather than blindly adding more endpoint calls.

The goal is to retrieve useful schedule coverage with a small number of targeted requests. The script deliberately avoids scanning historical scoreboard dates just to reconstruct a current schedule.

## iCalendar

Create an `.ics` file:

```bash
python3 espn2ics.py --team "Liverpool" --ical
```

Specify the filename:

```bash
python3 espn2ics.py --team "Liverpool" --ical Liverpool.ics
```

This produces a standard iCalendar file containing the schedule, venue, sport, and league information.

## JSON

Create a JSON copy of the schedule:

```bash
python3 espn2ics.py --team "Portland Timbers" --sport soccer --json
```

JSON files are automatically written to the `json/` directory using the team name:

```text
json/
└── Portland_Timbers.json
```

A custom filename can also be specified:

```bash
python3 espn2ics.py --team "Portland Timbers" --sport soccer --json timbers.json
```

The JSON output is written to the file and is not printed to stdout.

## Soccer

Soccer requires some competition-specific handling because a team can appear in multiple ESPN soccer leagues or competitions.

For soccer, the script uses ESPN's broader schedule endpoints and configured competition routes, then merges and deduplicates the returned events. This is intended to capture league, cup, continental, playoff/knockout, and friendly fixtures when ESPN exposes them through its schedule data.

Configured soccer competitions include:

```text
English Premier League
La Liga
Bundesliga
Serie A
Ligue 1
Eredivisie
Primeira Liga
Scottish Premiership
Belgian Pro League
Turkish Super Lig
MLS
NWSL
Liga MX
UEFA Champions League
UEFA Europa League
UEFA Conference League
Club Friendly
...
```

This is particularly useful for clubs such as Manchester City, where league matches and Club Friendly matches may be exposed through different ESPN routes.

The script only keeps events from today forward. It does not walk backward through scoreboard dates looking for completed matches.

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
python3 espn2ics.py --help
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
filter current/future events
    ↓
sort_events()
    ↓
print_schedule()
    ↓
create_ical_if_requested()
    ↓
create_json_if_requested()
    ↓
print API request count
```

Sport-specific API differences are kept inside the schedule retrieval layer rather than spreading ESPN-specific conditionals through `main()`.

## ESPN API notes

This project uses ESPN's publicly accessible site/core API endpoints rather than an official paid developer API.

ESPN's endpoints are not guaranteed to remain stable. Some competitions use different endpoints or expose incomplete current/future data. The script therefore treats team discovery and schedule retrieval separately and uses competition-specific handling where necessary.

Because this tool is designed as a **current/upcoming schedule finder**, it intentionally does not provide a `--season` option or attempt to reconstruct historical seasons.

## Examples

```bash
# EPL
python3 espn2ics.py --team "Liverpool"

# NCAA football
python3 espn2ics.py --team "Oregon Ducks" --sport football

# NCAA baseball
python3 espn2ics.py --team "Oregon Ducks" --sport baseball

# NWSL
python3 espn2ics.py --team "Portland Thorns" --sport soccer

# WNBA
python3 espn2ics.py --team "Portland Fire" --sport basketball

# NHL
python3 espn2ics.py --team "Boston Bruins" --sport hockey

# iCalendar
python3 espn2ics.py --team "Liverpool" --ical

# JSON
python3 espn2ics.py --team "Portland Timbers" --sport soccer --json
```
