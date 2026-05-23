from flask import Flask, jsonify
from flask_cors import CORS
from api.users import userAPI
from config import Config
from extensions import init_mongo
from messages import start_message, success_message

"""
    App server for the application
"""

# Initialize the Flask app
app = Flask(__name__)
CORS(app)

# Configure the app
CONFIG = Config()
app.config["MONGODB_URI"] = CONFIG["database"]["uri"]

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


# Register the blueprints
app.register_blueprint(userAPI)


if __name__ == "__main__":
    # Initialize the MongoDB extension
    init_mongo(app)

    # Run the app
    app.run(
        host="0.0.0.0", 
        port=CONFIG["server"]["port"], 
        debug=CONFIG["server"]["debug"]
    )
