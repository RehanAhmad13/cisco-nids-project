import re
import os
import datetime as dt
from typing import List, Tuple, Dict

import pandas as pd
from netmiko import ConnectHandler
from sqlalchemy import create_engine
import pytz
import time


# ======================================
# SSH Connection Helper Function 
# ======================================
def connect_device(host, username, password, device_type="cisco_ios", **extra_settings):
    connection_settings = {
        "host": host,
        "username": username,
        "password": password,
        "device_type": device_type,
        "fast_cli": True,
        "session_timeout": 30,
        "banner_timeout": 30,
        "auth_timeout": 20,
        **extra_settings
    }
    return ConnectHandler(**connection_settings)


# ======================================
# Flow Parsing Helpers
# ======================================


#_COL_SPLIT is  a regular expresson. If the router gives an output: 
# "IPV4 SRC ADDR  IPV4 DST ADDR  TRNS SRC PORT"
# _COL_SPLIT will split it into: 
#    ["ipv4_src_addr", "ipv4_dst_addr", "trns_src_port"]

_COL_SPLIT = re.compile(r"\s{2,}")  # two or more spaces




#The following dictionary maps the column names from the Cisco 
#IOS output to the column names used in the NIDS (Network Intrusion 
#Detection System) database.


IOS2NIDS = {
    "IPV4 SRC ADDR": "IPV4_SRC_ADDR",
    "IPV4 DST ADDR": "IPV4_DST_ADDR",
    "TRNS SRC PORT": "L4_SRC_PORT",
    "TRNS DST PORT": "L4_DST_PORT",
    "IP PROT":       "PROTOCOL",
    "tcp flags":     "TCP_FLAGS",
    "bytes long":    "IN_BYTES",
    "pkts long":     "IN_PKTS",
    "APP NAME":      "L7_PROTO",  # optional
}


def _parse_header(lines: List[str]) -> Tuple[int, List[str]]:
    for idx, ln in enumerate(lines):
        if "IPV4 SRC ADDR" in ln and "IPV4 DST ADDR" in ln:
            cols = _COL_SPLIT.split(ln.strip())
            return idx, cols
    raise ValueError("Flexible NetFlow header not found")



### This is our main parser function. It starts reading after the 
### head line. Skips blank lines and then splits the line into parts.
### Create a dictionary for each flow. For example, 
### [ {'IPV4 SRC ADDR': '192.168.1.1',
#      'IPV4 DST ADDR': '8.8.8.8',
#      'TRNS SRC PORT': '12345',
#      .... 
#     } 
#
#     {
#      ....
#     }
#  ]

def _parse_flow_lines(lines: List[str], start_idx: int, headers: List[str]) -> List[Dict[str, str]]:
    data = []
    for ln in lines[start_idx+2:]:
        if not ln.strip():
            break
        parts = _COL_SPLIT.split(ln.rstrip())
        if len(parts) != len(headers):
            continue
        data.append(dict(zip(headers, parts)))
    return data

# ======================================
# NetFlow Fetch + DataFrame Build
# ======================================
def fetch_monitor_cache(conn: ConnectHandler, monitor: str) -> pd.DataFrame:
    
    ## This function fetches the flow monitor cache from the router.
    raw = conn.send_command(f"show flow monitor {monitor} cache", use_textfsm=False)
    ### Split the output into lines
    lines = raw.splitlines()
    ### Find the header line and its index. Splits into a list of columns
    hdr_idx, hdr_cols = _parse_header(lines)
    ### This parses the flow lines and creates a list of dictionaries
    rows = _parse_flow_lines(lines, hdr_idx, hdr_cols)

    if not rows:
        return pd.DataFrame()

    ### We create a dataframe. The columns are renamed according to the IOS2NIDS mapping.
    df = pd.DataFrame(rows).rename(columns=IOS2NIDS)

    ### Convert columns to numeric types from strings. 
    for col in ("IN_BYTES", "IN_PKTS", "L4_SRC_PORT", "L4_DST_PORT"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convert hex to integer
    if "TCP_FLAGS" in df.columns:
        df["TCP_FLAGS"] = df["TCP_FLAGS"].apply(
            lambda x: int(x, 16) if isinstance(x, str) and x.startswith("0x") else pd.NA
        )

    # Check if both 'time first' and 'time last' columns exist in the DataFrame
    if {"time first", "time last"}.issubset(df.columns):

        # Get today's date in 'YYYY-MM-DD' format (e.g., '2025-04-27')
        today = dt.date.today().isoformat()

        # Combine today's date with the 'time first' column to make a full timestamp
        # Example: '2025-04-27 10:30:15'
        first = pd.to_datetime(today + " " + df["time first"])

        # Similarly, combine today's date with the 'time last' column
        last = pd.to_datetime(today + " " + df["time last"])

        # Handle flows that cross midnight:
        # If the 'last' timestamp is earlier than 'first' (flow crossed into next day),
        # add 1 day to the 'last' timestamp to correct it
        last = last.where(last >= first, last + pd.Timedelta(days=1))

        # Define the Dubai timezone
        dubai_tz = pytz.timezone("Asia/Dubai")

        # First assume timestamps are in UTC, then convert them to Dubai local time
        df["time_first"] = first.dt.tz_localize("UTC").dt.tz_convert(dubai_tz)
        df["time_last"]  = last.dt.tz_localize("UTC").dt.tz_convert(dubai_tz)

        # Calculate flow duration in milliseconds
        # (time_last - time_first) gives timedelta → convert to seconds → multiply by 1000 to get milliseconds
        df["FLOW_DURATION_MILLISECONDS"] = (last - first).dt.total_seconds() * 1000

        # Also calculate duration in seconds for later use
        dur_sec = df["FLOW_DURATION_MILLISECONDS"] / 1000.0

        # Calculate bytes transferred per second
        # (Total bytes) / (Duration in seconds), avoiding division by 0
        df["SRC_TO_DST_SECOND_BYTES"] = df["IN_BYTES"] / dur_sec.replace(0, pd.NA)

        # Calculate average throughput (in bits per second)
        # 8 bits per byte × (Total bytes) / (Duration in seconds)
        df["SRC_TO_DST_AVG_THROUGHPUT"] = 8 * df["IN_BYTES"] / dur_sec.replace(0, pd.NA)

        # Set the scrape timestamp as the 'time_last' value (when flow ended)
        df["SCRAPE_TIMESTAMP"] = df["time_last"]

    else:
        # If 'time first' and 'time last' columns are missing,
        # fall back to setting scrape timestamp as the current time (Dubai timezone)
        df["SCRAPE_TIMESTAMP"] = pd.Timestamp.now(tz=pytz.timezone("Asia/Dubai"))

    # Always add the monitor name (like "FLOW-MONITOR") into a new column
    df["FLOW_MONITOR"] = monitor

    return df


def scrape_all_monitors(conn: ConnectHandler, monitors: List[str]) -> pd.DataFrame:
    frames = [fetch_monitor_cache(conn, m) for m in monitors]
    return pd.concat(frames, ignore_index=True)

# ======================================
# Writers: TimescaleDB & CSV
# ======================================
def write_to_timescaledb(df: pd.DataFrame, engine):
    # Drop unused Cisco-style columns if they exist
    df = df.drop(columns=["time first", "time last"], errors="ignore")

    df = df.rename(columns={
        "IPV4_SRC_ADDR": "ipv4_src_addr",
        "IPV4_DST_ADDR": "ipv4_dst_addr",
        "L4_SRC_PORT": "l4_src_port",
        "L4_DST_PORT": "l4_dst_port",
        "PROTOCOL": "protocol",
        "TCP_FLAGS": "tcp_flags",
        "IN_BYTES": "in_bytes",
        "IN_PKTS": "in_pkts",
        "FLOW_DURATION_MILLISECONDS": "flow_duration_ms",
        "SRC_TO_DST_SECOND_BYTES": "bytes_per_second",
        "SRC_TO_DST_AVG_THROUGHPUT": "avg_throughput_bps",
        "FLOW_MONITOR": "flow_monitor",
        "SCRAPE_TIMESTAMP": "time"
    })

    df.to_sql("network_flows", con=engine, if_exists="append", index=False, method="multi")

def write_to_csv(df: pd.DataFrame, filename="flows_log.csv"):
    file_exists = os.path.isfile(filename)
    df.to_csv(filename, mode='a', header=not file_exists, index=False)

# ======================================
# Main: Scrape & Log
# ======================================

if __name__ == "__main__":
    host     = "[REDACTED_IP]"
    username = "usama"
    password = "usama"
    monitors = ["FLOW-MONITOR", "dat_Gi1_885011376"]

    tsdb_url = "postgresql+psycopg2://[REDACTED]:[REDACTED]@localhost:5432/network_db"
    tsdb_engine = create_engine(tsdb_url)

    while True:
        print("Connecting to router...")
        try:
            conn = connect_device(host, username, password)
            df = scrape_all_monitors(conn, monitors)
            conn.disconnect()

            if not df.empty:
                print("Extracted features:")
                print(df.head().to_string(index=False))

                print("Writing to TimescaleDB and CSV...")
                write_to_csv(df)
                write_to_timescaledb(df, tsdb_engine)

                print(f"Logged {len(df)} flows.")
            else:
                print("No flows found.")

        except Exception as e:
            print(f"Error: {e}")

        print("Sleeping for 1 minutes...\n")
        time.sleep(60)  # 1 minutes
