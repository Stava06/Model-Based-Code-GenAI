from flask import Flask, jsonify
from flask_cors import CORS
from api.agent_api import agentAPI
from api.users import userAPI
from config import Config
from extensions import init_mongo
from messages import start_message, success_message, error_message
import socket


"""
    App server for the application
"""

# Initialize the Flask app
app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    start_message('main')

    answer = {
        "service": "appserver",
        "message": "ok",
        "config": {
            "database": {
                "is_ready": CONFIG["database"]["uri"] is not None,
                "name": CONFIG["database"]["name"],
                "user_collection": CONFIG["database"]["user_collection"]
            },
            "server": {
                "port": CONFIG["server"]["port"],
                "debug": CONFIG["server"]["debug"]
            }
        }
    }

    success_message('main', "Index page loaded successfully")
    return jsonify(answer), 200

if __name__ == "__main__":
    # Configure the app
    CONFIG = Config()
    app.config["MONGODB_URI"] = CONFIG["database"]["uri"]

    # Register the blueprints
    app.register_blueprint(userAPI)
    app.register_blueprint(agentAPI)

    # Get the port
    port = int(CONFIG["server"]["port"])
    is_port_available = False
    while not is_port_available or port > 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                print(f'Port {port} is already in use. Changing to port {port + 1}')
                port += 1
            else:
                is_port_available = True

    if port > 65535:
        error_message('server', 'No port available')
        exit(1)
    else:
        success_message('server', f'Running on port {port}')
    
    # Run the app
    app.run(
        host="0.0.0.0",
        port=port,
        debug=CONFIG["server"]["debug"],
    )
