# Multi-DB Select

Run one `SELECT` across more than one SQL Server. Check the servers to
include, then load their databases with `SELECT name FROM sys.databases`.

## Servers

| Name | Host | IP |
| --- | --- | --- |
| Butterfly | sql-butterfly.appian.trimblemaps.com | 192.168.224.66 |
| Tadpole | sql-tadpole.appian.trimblemaps.com | 192.168.224.205 |
| Milky Way | sql-milkyway.appian.trimblemaps.com | 192.168.224.202 |
| Fireworks | sql-fireworks.appian.trimblemaps.com | 192.168.224.80 |
| LAW SQL 01 | law-sql01.appian.trimblemaps.com | 192.168.224.174 |
| 10.228.2.38 | — | 10.228.2.38 |
| 192.168.224.61 | — | 192.168.224.61 |
| SQL 01 Staging | sql01.staging.appiantesting.com | 192.168.208.48 |
| LAW SQL 02 Staging | law-sql02.staging.appiantesting.com | 192.168.208.48 |

IPs are resolved from DNS when the page loads, and fall back to the values
above if lookup fails.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

SQL credentials can be entered on the page, or stored in a local `.env`
file based on `.env.example`:

```
MSSQL_USER=your_user
MSSQL_PASSWORD=your_password
```

On Windows, check **Windows authentication** (or set `MSSQL_WINDOWS_AUTH=1`)
to use the current login instead of SQL authentication.

## Tests

```bash
pytest
```
