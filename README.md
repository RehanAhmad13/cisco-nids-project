# Cisco NIDS Project

This repository contains a network intrusion detection dashboard using Flask and TimescaleDB. Sensitive credentials have been removed. Configure the following environment variables before running any scripts:

- `TSDB_URL` – Connection string for the TimescaleDB/PostgreSQL instance, e.g. `postgresql://user:pass@host:5432/network_db`.
- `DEVICE_HOST` – IP or hostname of the Cisco device to scrape.
- `DEVICE_USERNAME` – SSH username for the device.
- `DEVICE_PASSWORD` – SSH password for the device.

Create a `.env` file or export these variables in your shell. The `.env` file is ignored by git.

Install requirements and run the app:

```bash
pip install -r requirements.txt
python app.py
```
