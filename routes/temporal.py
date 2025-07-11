from flask import Blueprint, render_template
import pandas as pd
from utils.db import get_conn

temporal_bp = Blueprint('temporal', __name__)

@temporal_bp.route("/temporal")
def temporal():
    conn = get_conn()
    query = """
        SELECT time_first
        FROM network_flows
        WHERE time_first > NOW() - INTERVAL '7 days'
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        flows_by_hour = {}
        flows_by_day = {}
        heatmap_data = []
    else:
        df['time_first'] = pd.to_datetime(df['time_first'])
        df['hour'] = df['time_first'].dt.hour
        df['day_of_week'] = df['time_first'].dt.dayofweek

        # Flows by Hour
        flows_by_hour = df['hour'].value_counts().sort_index().to_dict()

        # Flows by Day
        flows_by_day = df['day_of_week'].value_counts().sort_index().to_dict()

        # Heatmap Data
        heatmap_df = df.groupby(['day_of_week', 'hour']).size().unstack(fill_value=0)
        heatmap_data = heatmap_df.values.tolist()
        heatmap_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        heatmap_hours = list(range(24))

    return render_template('temporal.html',
                           flows_by_hour=flows_by_hour,
                           flows_by_day=flows_by_day,
                           heatmap_data=heatmap_data,
                           heatmap_days=heatmap_days,
                           heatmap_hours=heatmap_hours)
