# Cisco NetFlow NIDS

This was my first project of learning software development. Since many of the feature-extraction and device scraper abilities are used by more sophisticated softwares such as MonetX, this was a good starter project to get familiar with them. It is a Flask-based web application for collecting and visualizing NetFlow data from Cisco devices. The system scrapes flows via SSH, stores them in TimescaleDB, and offers dashboards for performance, behavior, temporal patterns, geolocation, and machine-learning predictions.

---

## Features

- **Real-time Flow Collection**  
  `scraper.py` gathers NetFlow cache data from a Cisco device using `netmiko`.

- **TimescaleDB Storage**  
  Flows are written to a PostgreSQL/TimescaleDB instance for efficient querying.

- **Web Dashboard** – Multiple Flask + Plotly pages:
  - `/` – Live metrics and latest flows
  - `/performance` – Flow duration and TCP flag stats
  - `/behavior` – Port usage and protocol distribution
  - `/temporal` – Hourly/daily flow patterns
  - `/geomap` – Geolocated flow sources on a map
  - `/ml-predictions` – Anomaly labels from an XGBoost model
  - `/traffic_by_application` – Traffic grouped by application name

- **ML Training**  
  `Training_Script/xg_boost_11.py` demonstrates training an XGBoost model on the NF-UQ-NIDS dataset (*dataset not included*).

---

## Setup

### Python Requirements

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
