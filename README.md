# Multi-DB Select

Run one `SELECT` across more than one SQL Server. Check production and
staging hosts, load their databases, then run the same query against the
databases you pick.

## Servers

| Name | Host | IP | Environment |
| --- | --- | --- | --- |
| Butterfly | sql-butterfly.appian.trimblemaps.com | 192.168.224.66 | Production |
| Tadpole | sql-tadpole.appian.trimblemaps.com | 192.168.224.205 | Production |
| Milky Way | sql-milkyway.appian.trimblemaps.com | 192.168.224.202 | Production |
| Fireworks | sql-fireworks.appian.trimblemaps.com | 192.168.224.80 | Production |
| LAW SQL 01 | law-sql01.appian.trimblemaps.com | 192.168.224.174 | Production |
| 10.228.2.38 | — | 10.228.2.38 | Production |
| 192.168.224.61 | — | 192.168.224.61 | Production |
| SQL 01 Staging | sql01.staging.appiantesting.com | 192.168.208.48 | Staging |
| LAW SQL 02 Staging | law-sql02.staging.appiantesting.com | 192.168.208.48 | Staging |

IPs are resolved from DNS when the page loads, and fall back to the values
above if lookup fails.

## Run locally

On Windows, from the repo root (or double-click `launch.bat`):

```bat
launch.bat
```

That is the same pattern as the TBLINISETTINGS instance compare repo: `launch.bat` calls `scripts\launch.py`, which creates `.venv`, installs Python packages, copies `.env.example` to `.env` if needed, starts the site, and opens [http://127.0.0.1:5000](http://127.0.0.1:5000).

You can also run the launcher directly:

```bat
scripts\launch.bat
```

or:

```bash
python3 scripts/launch.py
```

Manual setup still works:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Production and staging use separate SQL logins. Enter them on the page,
or store them in a local `.env` file based on `.env.example`:

```
MSSQL_PROD_USER=prod_user
MSSQL_PROD_PASSWORD=prod_password
MSSQL_STAGE_USER=stage_user
MSSQL_STAGE_PASSWORD=stage_password
```

The query box accepts a single `SELECT` (including `WITH` CTEs). It runs
against every checked database, using the credentials that match that
server's environment.

## Tests

```bash
pytest
```
