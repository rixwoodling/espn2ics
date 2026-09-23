# ESPN Schedule to iCalendar

Find a sports team through ESPN and retrieve its **current and upcoming schedule**.

```text
$ python3 espn2ics.py --team "Mets" --sport baseball --ical

Finding team: Mets
Team: New York Mets
Team ID: 21
Sport: baseball
League: MLB

Schedule:
--------------------------------------------------------------------------------
2026-09-22 17:05  New York Mets at Texas Rangers  [TV: MLB.TV, SNY]  @ Globe Life Field
2026-09-23 17:05  New York Mets at Texas Rangers  [TV: MLB.TV, SNY]  @ Globe Life Field
2026-09-24 11:35  New York Mets at Texas Rangers  [TV: MLB.TV, SNY]  @ Globe Life Field
2026-09-25 15:45  New York Mets at Washington Nationals  [TV: MLB.TV]  @ Nationals Park
2026-09-26 13:05  New York Mets at Washington Nationals  [TV: ESPN]  @ Nationals Park
2026-09-27 12:05  New York Mets at Washington Nationals  [TV: MLB.TV]  @ Nationals Park

Found 6 event(s).
Created JSON: ical/New_York_Mets.ical
API requests: 3
```

## Usage

```bash
python3 espn2ics.py --team "Liverpool"
```

Use `--sport` when needed:

```bash
python3 espn2ics.py --team "Oregon Ducks" --sport football
python3 espn2ics.py --team "Oregon Ducks" --sport baseball
```

Supported sports:

```text
baseball
basketball
football
hockey
soccer
```

The schedule contains **today and future events only**.

## iCalendar

Create an iCalendar file:

```bash
python3 espn2ics.py --team "Liverpool" --ical
```

Files are written to `ical/`:

```text
ical/
└── Liverpool.ics
```

Specify a filename:

```bash
python3 espn2ics.py --team "Liverpool" --ical Liverpool.ics
```

Calendar events include the venue and TV information when ESPN provides it.

## JSON

Create JSON output:

```bash
python3 espn2ics.py --team "Portland Timbers" --sport soccer --json
```

Files are written to `json/`:

```text
json/
└── Portland_Timbers.json
```

Specify a filename:

```bash
python3 espn2ics.py --team "Portland Timbers" --sport soccer --json timbers.json
```

## Sports

The script currently supports:

- MLB
- NCAA Baseball
- NBA
- WNBA
- NCAA Basketball
- NFL
- NCAA Football
- NHL
- NCAA Hockey
- Soccer

Soccer competitions include major domestic leagues, MLS, NWSL, Liga MX, UEFA competitions, and Club Friendly matches.

Rugby is not currently supported.

## Schedule handling

Sport and league-specific ESPN behavior is isolated in dedicated schedule handlers.

This is especially important for leagues such as:

- **NBA**, which uses dynamic season selection
- **NHL**, which requires ESPN's current season and regular-season type
- **Soccer**, where a club can appear across multiple competitions

The rest of the application uses shared code for team discovery, filtering, formatting, JSON, iCalendar, and API request counting.

## API requests

Each run reports the number of ESPN API requests:

```text
Found 6 event(s).
API requests: 3
```

The script avoids scanning historical scoreboard dates and is designed to retrieve current/upcoming schedules with a small number of requests.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install requests icalendar
```

Then:

```bash
python3 espn2ics.py --help
```

## Examples

```bash
# MLB
python3 espn2ics.py --team "Mets" --sport baseball

# NBA
python3 espn2ics.py --team "Portland Trail Blazers" --sport basketball

# NFL
python3 espn2ics.py --team "Seattle Seahawks" --sport football

# NCAA Football
python3 espn2ics.py --team "Oregon Ducks" --sport football

# NHL
python3 espn2ics.py --team "Boston Bruins" --sport hockey

# NWSL
python3 espn2ics.py --team "Portland Thorns" --sport soccer

# iCalendar
python3 espn2ics.py --team "Liverpool" --ical

# JSON
python3 espn2ics.py --team "Portland Timbers" --sport soccer --json
```

## ESPN API

This project uses ESPN's publicly accessible site/core API endpoints.

ESPN does not provide a guaranteed stable public API for this use case, so endpoint behavior may change over time.
