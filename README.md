# Multi-DB Select

Run one `SELECT` across more than one SQL Server. This first slice is the
server picker: a checkbox list of Appian SQL hosts, with names and IPs.

## Servers

| Name | Host | IP |
| --- | --- | --- |
| Butterfly | sql-butterfly.appian.trimblemaps.com | 192.168.224.66 |
| Tadpole | sql-tadpole.appian.trimblemaps.com | 192.168.224.205 |
| Milky Way | sql-milkyway.appian.trimblemaps.com | 192.168.224.202 |
| Fireworks | sql-fireworks.appian.trimblemaps.com | 192.168.224.80 |
| LAW SQL 01 | law-sql01.appian.trimblemaps.com | 192.168.224.174 |

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

## Tests

```bash
pytest
```
