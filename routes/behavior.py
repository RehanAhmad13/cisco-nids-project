from flask import Blueprint, render_template
import psycopg2
import pandas as pd

behavior_bp = Blueprint('behavior', __name__)

@behavior_bp.route("/behavior")
def behavior():
    conn = psycopg2.connect(
        dbname="network_db", user="postgres", password="postgres", host="localhost", port="5432"
    )
    query = """
        SELECT ipv4_src_addr, ipv4_dst_addr, l4_src_port, l4_dst_port, protocol, time_first
        FROM network_flows
        WHERE time_first > NOW() - INTERVAL '30 minutes'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        flow_recurrence = {}
        port_usage = {}
        protocol_dist = {}
    else:
        # Flow Recurrence: (source IP, destination IP) pair counts
        flow_recurrence = (df.groupby(["ipv4_src_addr", "ipv4_dst_addr"])
                             .size()
                             .sort_values(ascending=False)
                             .head(10)
                             .to_dict())

        # Port Usage: Destination ports count
        port_usage = (df['l4_dst_port']
                      .value_counts()
                      .head(10)
                      .to_dict())

        # Protocol Distribution (mapping TCP/UDP/ICMP)
        protocol_dist = (df['protocol']
                         .map({6: "TCP", 17: "UDP", 1: "ICMP"})
                         .fillna("Other")
                         .value_counts(normalize=True) * 100
                         ).round(2).to_dict()

    return render_template('behavior.html',
                           flow_recurrence=flow_recurrence,
                           port_usage=port_usage,
                           protocol_dist=protocol_dist)
