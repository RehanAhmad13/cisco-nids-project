from flask import Blueprint, render_template, jsonify
import pandas as pd
import pytz
from sqlalchemy import create_engine

dashboard_bp = Blueprint('dashboard', __name__)
engine = create_engine("postgresql+psycopg2://postgres:postgres@localhost:5432/network_db")

# -------------------
# Renders the main dashboard page
# -------------------
@dashboard_bp.route("/")
def dashboard():
    return render_template("index.html")

# -------------------
# Helper: Get flow data
# -------------------
def get_data():
    df = pd.read_sql("""
        SELECT time, time_first, time_last,
               ipv4_src_addr, ipv4_dst_addr,
               l4_src_port, l4_dst_port,
               protocol, tcp_flags,
               in_bytes, in_pkts,
               flow_duration_ms, bytes_per_second,
               avg_throughput_bps, flow_monitor
        FROM network_flows
        WHERE time_first > NOW() - interval '5 minutes'
        ORDER BY time_first DESC
        LIMIT 1000
    """, engine)

    dubai_tz = pytz.timezone("Asia/Dubai")
    for col in ["time", "time_first", "time_last"]:
        df[col] = pd.to_datetime(df[col]).dt.tz_convert(dubai_tz).astype(str)

    return df

# -------------------
# API: Return flow data
# -------------------
@dashboard_bp.route("/data")
def data():
    try:
        df = get_data()
        return jsonify(df.replace({float('nan'): None}).to_dict(orient="records"))
    except Exception as e:
        print("Error in /data:", e)
        return jsonify({"error": str(e)}), 500

# -------------------
# API: Return metrics data
# -------------------

"""
This API aggregates flow data into 5 key metrics:
1. In Bytes Over Time
2. In Packets Over Time
3. Average Throughput (bps) Over Time
4. Flow Count Per Minute
5. Top Talkers (by source IP and total bytes sent)

 """


@dashboard_bp.route("/metrics")
def metrics():
    try:
        query = """
            SELECT
                date_trunc('minute', time_first) AT TIME ZONE 'Asia/Dubai' AS minute,
                SUM(in_bytes) AS total_bytes,
                SUM(in_pkts) AS total_packets,
                COUNT(*) AS flow_count,
                AVG(avg_throughput_bps) AS avg_throughput
            FROM network_flows
            WHERE time_first > NOW() - interval '30 minutes'
            GROUP BY minute
            ORDER BY minute ASC;
        """

        talkers_query = """
            SELECT ipv4_src_addr, SUM(in_bytes) AS total_bytes
            FROM network_flows
            WHERE time_first > NOW() - interval '30 minutes'
            GROUP BY ipv4_src_addr
            ORDER BY total_bytes DESC
            LIMIT 10;
        """

        df_metrics = pd.read_sql(query, engine)
        df_talkers = pd.read_sql(talkers_query, engine)

        df_metrics["minute"] = pd.to_datetime(df_metrics["minute"]).dt.strftime("%Y-%m-%dT%H:%M:%S")

        return jsonify({
            "timeseries": df_metrics.replace({float('nan'): None}).to_dict(orient="records"),
            "top_talkers": df_talkers.replace({float('nan'): None}).to_dict(orient="records")
        })

    except Exception as e:
        print("Error in /metrics:", e)
        return jsonify({"error": str(e)}), 500
