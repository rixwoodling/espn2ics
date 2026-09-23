# ESPN Schedule to iCalendar

A small Python command-line tool for finding sports teams through ESPN and retrieving their **current and upcoming schedules**, with optional iCalendar and JSON output.

## `espn2ics.py`

The script searches the supported ESPN sports and retrieves events from **today forward**.

It does not require a season argument and does not scan historical scoreboard dates to reconstruct a schedule.

The goal is simple: give it a team name, let ESPN determine the team and competition, and get a usable current/upcoming schedule without having to manually know ESPN's internal league IDs.

### What's new in current version

Current version refactors schedule retrieval so that **league-specific behavior is isolated**.

Instead of putting sport-specific ESPN logic into one large conditional function, current version routes each sport/league through its own schedule handler:

```text
get_schedule()
    ↓
SCHEDULE_HANDLERS
    ├── NBA
    ├── WNBA
    ├── NFL
    ├── NCAA Football
    ├── NHL
    ├── NCAA Hockey
    ├── MLB
    ├── NCAA Baseball
    └── Soccer
```

This means changes to one league's ESPN endpoint should not require changes to another league's schedule logic.

Shared functionality remains centralized:

- ESPN API requests
- team discovery
- date parsing
- current/future filtering
- event sorting
- TV/broadcast extraction
- venue extraction
- console formatting
- JSON output
- iCalendar output
- API request counting

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

## League-specific schedule handling

current version uses a central handler table:

```python
SCHEDULE_HANDLERS = {
    ("basketball", "nba"): get_current_nba_schedule,
    ("basketball", "wnba"): get_current_wnba_schedule,

    ("football", "nfl"): get_current_nfl_schedule,
    ("football", "college-football"): get_current_ncaa_football_schedule,

    ("hockey", "nhl"): get_current_nhl_schedule,
    ("hockey", "mens-college-hockey"): get_current_college_hockey_schedule,

    ("baseball", "mlb"): get_current_mlb_schedule,
    ("baseball", "college-baseball"): get_current_ncaa_baseball_schedule,

    # Soccer competitions use the soccer schedule handler.
}
```

The dispatcher selects the handler using:

```text
(sport, league)
```

If a league does not have a dedicated handler, current version falls back to the generic current-schedule handler.

### Why this matters

ESPN does not expose every sport the same way.

For example:

- NBA season selection differs from NHL.
- NHL requires explicit regular-season handling.
- Soccer can span multiple competitions.
- College sports have their own ESPN league routes.
- Some leagues expose different amounts of future schedule data.

Keeping those differences inside isolated handlers makes the project easier to extend and reduces the chance that fixing one sport breaks another.

## API request count

The script reports the number of ESPN API requests made during each run:

```text
Found 37 event(s).
API requests: 8
```

This makes it possible to measure and optimize the schedule lookup rather than blindly adding more endpoint calls.

The goal is to retrieve useful schedule coverage with a small number of targeted requests.

The script deliberately avoids scanning historical scoreboard dates just to reconstruct a current schedule.

## iCalendar

Create an `.ics` file:

```bash
python3 espn2ics.py --team "Liverpool" --ical
```

Specify the filename:

```bash
python3 espn2ics.py --team "Liverpool" --ical Liverpool.ics
```

iCalendar files are automatically written to the `ical/` directory.

For example:

```text
ical/
└── Liverpool.ics
```

The calendar contains:

- event date/time
- event name
- venue
- sport
- league
- TV/broadcast information when ESPN provides it

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

Broadcast information is included when ESPN supplies U.S. broadcast metadata.

## Soccer

Soccer requires special handling because a club can appear in multiple ESPN soccer leagues or competitions.

For soccer, the script uses ESPN's broader schedule endpoints and configured competition routes, then merges and deduplicates returned events.

This is intended to capture league, cup, continental, playoff/knockout, and friendly fixtures when ESPN exposes them through its schedule data.

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
```

This is particularly useful for clubs such as Manchester City, where league matches and Club Friendly matches may be exposed through different ESPN routes.

The script only keeps events from today forward.

It does not walk backward through scoreboard dates looking for completed matches.

## NBA

NBA schedule retrieval has its own handler in current version.

ESPN labels NBA seasons by the year in which they end, so current version determines the appropriate season dynamically:

```text
January through June
    → current calendar year

July through December
    → following calendar year
```

No `--season` argument is required.

Example:

```bash
python3 espn2ics.py --team "Portland Trail Blazers" --sport basketball
```

## NHL

NHL schedule retrieval also has its own isolated handler.

NHL seasons are discovered dynamically from ESPN's Core calendar rather than relying on a hard-coded season number.

The regular season is explicitly requested using ESPN's regular-season season type.

Example:

```bash
python3 espn2ics.py --team "Boston Bruins" --sport hockey
```

This allows current version to retrieve the current/upcoming regular-season schedule without requiring a manually supplied NHL season.

## Team discovery

Team discovery is separate from schedule retrieval.

The script:

1. Searches the configured ESPN league routes.
2. Scores candidate team-name matches.
3. Deduplicates candidates by ESPN team ID.
4. Selects the strongest match.
5. Reports ambiguity instead of guessing when multiple distinct ESPN teams match equally.

Example:

```bash
python3 espn2ics.py --team "Portland Trail Blazers" --sport basketball
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
league-specific schedule handler
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

Sport/league-specific ESPN behavior is kept inside the schedule retrieval layer rather than spreading ESPN-specific conditionals through `main()`.

## ESPN API notes

This project uses ESPN's publicly accessible site/core API endpoints rather than an official paid developer API.

ESPN's endpoints are not guaranteed to remain stable.

Some competitions use different endpoints or expose incomplete current/future data. The script therefore treats:

- team discovery
- schedule routing
- schedule retrieval
- output formatting

as separate concerns.

Competition-specific behavior belongs in the appropriate schedule handler.

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

# NBA
python3 espn2ics.py --team "Portland Trail Blazers" --sport basketball

# NHL
python3 espn2ics.py --team "Boston Bruins" --sport hockey

# NFL
python3 espn2ics.py --team "Seattle Seahawks" --sport football

# MLB
python3 espn2ics.py --team "Seattle Mariners" --sport baseball

# iCalendar
python3 espn2ics.py --team "Liverpool" --ical

# JSON
python3 espn2ics.py --team "Portland Timbers" --sport soccer --json
```

## Output directories

When output is requested, current version keeps generated files organized:

```text
project/
├── espn2ics.py
├── ical/
│   └── Team_Name.ics
└── json/
    └── Team_Name.json
```

The console remains focused on the human-readable schedule while JSON and iCalendar are written to their respective directories.
