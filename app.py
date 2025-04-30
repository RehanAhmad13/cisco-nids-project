from flask import Flask
from routes.dashboard import dashboard_bp
from routes.ml_inference import ml_bp
from routes.performance import performance_bp
from routes.behavior import behavior_bp
from routes.temporal import temporal_bp

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(dashboard_bp)
app.register_blueprint(ml_bp)
app.register_blueprint(performance_bp)
app.register_blueprint(behavior_bp)
app.register_blueprint(temporal_bp)

if __name__ == "__main__":
    app.run(debug=True)
