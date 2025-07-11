from flask import Blueprint, render_template, jsonify
import geoip2.database
import pandas as pd
import os
from sqlalchemy import create_engine
from dotenv import load_dotenv
from config import get_database_url

load_dotenv()

geomap_bp = Blueprint('geomap', __name__)


@geomap_bp.route('/geomap')
def geomap_page():
    return render_template('geomap.html')

# --- invoking database engine ---
engine = create_engine(get_database_url())

# --- invoking GeoIP reader ---
reader = geoip2.database.Reader(os.path.join('data', 'GeoLite2-City.mmdb'))



@geomap_bp.route('/api/geomap_data')
def geomap_data():
    # Pulling the last 5 minutes of flows
    df = pd.read_sql(
        """
        SELECT ipv4_src_addr, time_first
        FROM network_flows
        WHERE time_first > NOW() - INTERVAL '5 minutes'
        """,
        engine,
        parse_dates=['time_first']
    )

    # Lookup lat/lon for each IP
    def lookup(ip):
        try:
            rec = reader.city(ip)
            return {'lat': rec.location.latitude, 'lon': rec.location.longitude}
        except Exception:
            return {'lat': None, 'lon': None}

    df['geo'] = df['ipv4_src_addr'].apply(lookup)

    # Converting to a plain list of dicts for jsonify
    records = []
    for idx, row in df.iterrows():
        geo = row['geo']
        if geo['lat'] is not None and geo['lon'] is not None:
            records.append({
                'ip': row['ipv4_src_addr'],
                'time': row['time_first'].isoformat(),
                'lat': geo['lat'],
                'lon': geo['lon']
            })

    return jsonify(records)