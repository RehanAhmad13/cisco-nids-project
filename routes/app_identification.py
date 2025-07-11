# routes/app_identification.py

from flask import Blueprint, render_template, jsonify, current_app
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from config import get_database_url

load_dotenv()

app_ident = Blueprint('app_ident', __name__)
engine = create_engine(get_database_url())

@app_ident.route("/traffic_by_application")
def traffic_by_application():
    return render_template("traffic_by_application.html")

@app_ident.route("/api/traffic_by_application")
def api_traffic_by_application():
    try:
        query = """
            SELECT
              time_bucket('5 minutes', time_first) AT TIME ZONE 'Asia/Dubai' AS interval_start,
              application_name,
              SUM(in_bytes)    AS total_bytes,
              COUNT(*)         AS flow_count
            FROM network_flows
            WHERE time_first > NOW() - INTERVAL '1 HOUR'
              AND application_name IS NOT NULL
            GROUP BY interval_start, application_name
            ORDER BY interval_start, application_name
        """
        df = pd.read_sql_query(query, engine)

        # Format for JSON
        df['interval_start'] = (
            pd.to_datetime(df['interval_start'])
              .dt.strftime('%Y-%m-%dT%H:%M:%S')
        )

        return jsonify(df.to_dict(orient='records'))

    except Exception as e:
        current_app.logger.exception("Error in /api/traffic_by_application")
        return jsonify({"error": str(e)}), 500
