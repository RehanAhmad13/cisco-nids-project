from flask import Blueprint, render_template
import numpy as np
from utils.db import get_conn

performance_bp = Blueprint('performance', __name__)

@performance_bp.route("/performance")
def performance():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT time_first, in_bytes, in_pkts, flow_duration_ms, tcp_flags
        FROM network_flows
        WHERE time_first > NOW() - INTERVAL '30 minutes'
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    flows = []
    for row in rows:
        flows.append({
            "time_first": row[0],
            "in_bytes": row[1] or 0,
            "in_pkts": row[2] or 0,
            "flow_duration_ms": row[3] or 1,
            "tcp_flags": row[4] or 0
        })

    durations = [flow['flow_duration_ms'] for flow in flows if flow['flow_duration_ms'] is not None]
    bytes_per_second_list = [(flow['in_bytes'] / (flow['flow_duration_ms'] / 1000.0)) if flow['flow_duration_ms'] > 0 else 0 for flow in flows]
    packets_per_second_list = [(flow['in_pkts'] / (flow['flow_duration_ms'] / 1000.0)) if flow['flow_duration_ms'] > 0 else 0 for flow in flows]

    avg_duration = np.mean(durations) if durations else 0
    min_duration = np.min(durations) if durations else 0
    max_duration = np.max(durations) if durations else 0
    stddev_duration = np.std(durations) if durations else 0
    tiny_flows_percentage = (sum(1 for d in durations if d < 100) / len(durations)) * 100 if durations else 0

    tcp_flag_counts = {}
    for flow in flows:
        flag = flow['tcp_flags']
        tcp_flag_counts[flag] = tcp_flag_counts.get(flag, 0) + 1

    zero_byte_flows = sum(1 for flow in flows if flow['in_bytes'] == 0)
    one_packet_flows = sum(1 for flow in flows if flow['in_pkts'] == 1)

    return render_template('performance.html',
                           avg_duration=avg_duration,
                           min_duration=min_duration,
                           max_duration=max_duration,
                           stddev_duration=stddev_duration,
                           tiny_flows_percentage=tiny_flows_percentage,
                           tcp_flag_counts=tcp_flag_counts,
                           durations=durations,
                           bytes_per_second_list=bytes_per_second_list,
                           packets_per_second_list=packets_per_second_list,
                           zero_byte_flows=zero_byte_flows,
                           one_packet_flows=one_packet_flows)
