import re
import os
import time
import datetime as dt
from typing import List, Tuple, Dict

import pandas as pd
import pytz
from netmiko import ConnectHandler
from sqlalchemy import create_engine

# ======================================
# Configuration
# ======================================
DEVICE = {
    'device_type': 'cisco_ios',
    'host': '192.168.10.14',
    'username': 'usama',
    'password': 'usama',
}

MAIN_MONITOR = "FLOW-MONITOR"
FLAG_MONITOR = "dat_Gi1_885011376"

TSDB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5432/network_db"
TSDB_ENGINE = create_engine(TSDB_URL)
CSV_FILE = "flows_log.csv"

# ======================================
# Helpers & Constants
# ======================================
_SPLIT = re.compile(r"\s{2,}")  # split on 2+ spaces
IF_MAP = {"Gi1": 1, "Gi2": 2, "Gi3": 3, "Null": 0}
DUBAI_TZ = pytz.timezone("Asia/Dubai")

def compute_direction(ing: int, egr: int) -> str:
    if ing == 0 and egr in (1,2,3):           return 'local-origin'
    if ing in (1,2) and egr == 3:            return 'outbound'
    if ing == 3 and egr in (1,2):            return 'inbound'
    if ing in (1,2) and egr in (1,2) and ing != egr:
        return 'lateral'
    if egr == 0:                             return 'dropped'
    return 'unknown'

def parse_header_and_rows(raw: str) -> Tuple[List[str], List[Dict[str,str]]]:
    lines = raw.splitlines()
    for idx, ln in enumerate(lines):
        if "IPV4 SRC ADDR" in ln:
            start = ln.index("IPV4 SRC ADDR")
            hdrs = [
                h.lower().replace(" ", "_")
                for h in _SPLIT.split(ln[start:].strip())
            ]
            rows = []
            for ln2 in lines[idx+2:]:
                part = ln2[start:].rstrip()
                if not part:
                    break
                parts = _SPLIT.split(part)
                if len(parts) == len(hdrs):
                    rows.append(dict(zip(hdrs, parts)))
            return hdrs, rows
    raise RuntimeError("Header not found in flow output")

def write_to_csv(df: pd.DataFrame, filename: str=CSV_FILE):
    header = not os.path.isfile(filename)
    df.to_csv(filename, mode='a', header=header, index=False)

def write_to_timescaledb(df: pd.DataFrame, engine):
    df.to_sql("network_flows", con=engine, if_exists="append", index=False, method="multi")

# ======================================
# Main loop
# ======================================
if __name__ == "__main__":
    while True:
        try:
            # 1) SSH & fetch both caches
            conn = ConnectHandler(**DEVICE)
            main_raw = conn.send_command(f"show flow monitor {MAIN_MONITOR} cache", use_textfsm=False)
            flag_raw = conn.send_command(f"show flow monitor {FLAG_MONITOR} cache", use_textfsm=False)
            conn.disconnect()

            # 2) Parse into DataFrames
            hdr_main, rows_main = parse_header_and_rows(main_raw)
            hdr_flag, rows_flag = parse_header_and_rows(flag_raw)
            df_main = pd.DataFrame(rows_main)
            df_flag = pd.DataFrame(rows_flag)

            # 3) Normalize column names
            common_rename = {
                "ipv4_src_addr":"ipv4_src_addr",
                "ipv4_dst_addr":"ipv4_dst_addr",
                "trns_src_port":"l4_src_port",
                "trns_dst_port":"l4_dst_port",
                "ip_prot":"protocol"
            }
            df_main = df_main.rename(columns=common_rename)
            df_flag = df_flag.rename(columns={**common_rename, "tcp_flags":"tcp_flags"})

            # 4) Ensure key columns exist and cast
            for df in (df_main, df_flag):
                for col in ("ipv4_src_addr","ipv4_dst_addr","l4_src_port","l4_dst_port","protocol"):
                    if col not in df.columns:
                        df[col] = pd.NA
                df["l4_src_port"] = pd.to_numeric(df["l4_src_port"], errors="coerce")
                df["l4_dst_port"] = pd.to_numeric(df["l4_dst_port"], errors="coerce")
                df["protocol"]    = pd.to_numeric(df["protocol"],    errors="coerce")

            # 5) Merge tcp_flags from flag monitor
            merge_keys = ["ipv4_src_addr","ipv4_dst_addr","l4_src_port","l4_dst_port","protocol"]
            df = pd.merge(
                df_main,
                df_flag[merge_keys + ["tcp_flags"]],
                on=merge_keys,
                how="left"
            )

            # 6) Rename raw cols and ensure full set
            col_map = {
                "bytes":"in_bytes","pkts":"in_pkts",
                "app_name":"application_name",
                "intf_input":"intf_input","intf_output":"intf_output",
                "time_first":"time_first","time_last":"time_last",
                "tcp_flags":"tcp_flags"
            }
            df = df.rename(columns=col_map)
            for c in col_map.values():
                if c not in df.columns:
                    df[c] = pd.NA

            # 7) Cast bytes/packets and tcp_flags
            df["in_bytes"] = pd.to_numeric(df["in_bytes"], errors="coerce")
            df["in_pkts"]  = pd.to_numeric(df["in_pkts"],  errors="coerce")
            df["tcp_flags"] = df["tcp_flags"].apply(
                lambda x: int(x,16) if isinstance(x,str) and x.startswith("0x") else pd.NA
            )

            # 8) Timestamps, durations & rates
            today = dt.date.today().isoformat()
            first = pd.to_datetime(today + " " + df["time_first"])
            last  = pd.to_datetime(today + " " + df["time_last"])
            last  = last.where(last>=first, last + pd.Timedelta(days=1))
            df["time_first"]       = first.dt.tz_localize("UTC").dt.tz_convert(DUBAI_TZ)
            df["time_last"]        = last.dt.tz_localize("UTC").dt.tz_convert(DUBAI_TZ)
            df["flow_duration_ms"] = (last - first).dt.total_seconds() * 1000

            df["dur_s"] = df["flow_duration_ms"] / 1000.0
            zero_dur    = df["flow_duration_ms"] == 0
            df.loc[zero_dur, ["bytes_per_second","avg_throughput_bps"]] = 0.0
            nonzero     = ~zero_dur
            df.loc[nonzero, "bytes_per_second"]   = df.loc[nonzero, "in_bytes"]    / df.loc[nonzero, "dur_s"]
            df.loc[nonzero, "avg_throughput_bps"] = df.loc[nonzero, "in_bytes"] * 8  / df.loc[nonzero, "dur_s"]
            df.drop(columns=["dur_s"], inplace=True)

            # 9) Scrape timestamp
            df["scrape_time"] = df["time_last"]

            # 10) Interfaces & direction
            df["ingress_if"] = df["intf_input"].map(IF_MAP).fillna(0).astype(int)
            df["egress_if"]  = df["intf_output"].map(IF_MAP).fillna(0).astype(int)
            df["direction"]  = df.apply(lambda r: compute_direction(r.ingress_if, r.egress_if), axis=1)

            # 11) Tag monitor and rename for TimescaleDB
            df["flow_monitor"] = MAIN_MONITOR
            df = df.rename(columns={"scrape_time": "time"})

            # 12) Select final columns
            final_cols = [
                "ipv4_src_addr","ipv4_dst_addr","l4_src_port","l4_dst_port",
                "protocol","tcp_flags","in_bytes","in_pkts",
                "flow_duration_ms","bytes_per_second","avg_throughput_bps",
                "application_name","ingress_if","egress_if","direction",
                "flow_monitor","time","time_first","time_last"
            ]
            df = df[final_cols]

            # 13) Output & write
            if not df.empty:
                print(f"Extracted {len(df)} flows, sample:")
                print(df.head().to_string(index=False))
                write_to_csv(df)
                write_to_timescaledb(df, TSDB_ENGINE)
            else:
                print("No flows found in this iteration.")

        except Exception as e:
            print(f"Error during scrape: {e}")

        print("Sleeping for 60 seconds...\n")
        time.sleep(60)
