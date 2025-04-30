import os
import joblib
import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, render_template
from sqlalchemy import create_engine
import xgboost as xgb
import sys
import socket
import struct

from utils.encoders import LabelEncoderExt

sys.modules['__main__'].LabelEncoderExt = LabelEncoderExt

ml_bp = Blueprint('ml_bp', __name__)

# === Paths ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENCODERS_PATH = os.path.join(BASE_DIR, "models", "ip_encoders_11.pkl")
MODEL_PATH = os.path.join(BASE_DIR, "models", "xgb_nids_model_11.json")

# === Load IP Encoders ===
encoders = joblib.load(ENCODERS_PATH)

# === Load XGBoost Model Properly ===
model = xgb.Booster()
model.load_model(MODEL_PATH)

# === Connect to TimescaleDB ===
TSDB_URL = "postgresql+psycopg2://[REDACTED]:[REDACTED]@localhost:5432/network_db"
engine = create_engine(TSDB_URL)

# === List of features expected ===
FEATURES = [
    "IPV4_SRC_ADDR", "IPV4_DST_ADDR", "L4_SRC_PORT", "L4_DST_PORT",
    "PROTOCOL", "TCP_FLAGS", "IN_BYTES", "IN_PKTS",
    "FLOW_DURATION_MILLISECONDS", "SRC_TO_DST_SECOND_BYTES", "SRC_TO_DST_AVG_THROUGHPUT"
]

# === Preprocessing helpers ===
def ip_to_int(ip_str):
    try:
        return struct.unpack("!I", socket.inet_aton(ip_str))[0]
    except Exception:
        return 0

def preprocess_row(row):
    """Preprocesses a single flow row to match model expectations."""
    src_ip = ip_to_int(row["ipv4_src_addr"])
    dst_ip = ip_to_int(row["ipv4_dst_addr"])
    features = [
        src_ip,
        dst_ip,
        row["l4_src_port"],
        row["l4_dst_port"],
        row["protocol"],
        row["tcp_flags"],
        row["in_bytes"],
        row["in_pkts"],
        row["flow_duration_ms"],
        row["bytes_per_second"],
        row["avg_throughput_bps"],
    ]
    return features

# === Route: Predict on last 100 flows ===
@ml_bp.route("/flows_with_predictions", methods=["GET"])
def flows_with_predictions():
    # Query last 100 flows
    query = """
    SELECT ipv4_src_addr, ipv4_dst_addr, l4_src_port, l4_dst_port,
           protocol, tcp_flags, in_bytes, in_pkts,
           flow_duration_ms, bytes_per_second, avg_throughput_bps,
           time
    FROM network_flows
    ORDER BY time DESC
    LIMIT 100;
    """
    df = pd.read_sql(query, engine)

    # Preprocess each row
    X_list = df.apply(preprocess_row, axis=1).tolist()

    # Create a DataFrame with correct feature names
    X_df = pd.DataFrame(X_list, columns=FEATURES)

    # Turn it into DMatrix for Booster
    dmatrix = xgb.DMatrix(X_df, feature_names=X_df.columns.tolist())

    # Make predictions
    preds = model.predict(dmatrix)

    # Attach predictions back
    df["prediction"] = ["Malicious" if p >= 0.5 else "Benign" for p in preds]

    # Convert to list of dicts for JSON
    results = df.to_dict(orient="records")

    return jsonify(results)

# === Route: ML Predictions Page ===
@ml_bp.route("/ml-predictions", methods=["GET"])
def ml_predictions_page():
    return render_template("ml_predictions.html")
