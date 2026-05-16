import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo.errors import PyMongoError

from api.users import userAPI
from config import CONFIG
from extensions import init_mongo
from messages import start_message, success_message, error_message

app = Flask(__name__)
CORS(app)

app.config["MONGODB_URI"] = CONFIG["database"]["uri"]

@app.get("/")
def index():
    start_message('main')

    success_message('main', "Index page loaded successfully")
    return jsonify({"service": "appserver", "message": "ok"}), 200


@app.get("/health")
def health():
    start_message('health')
    success_message('health', "Health check successful")
    return jsonify({"status": "healthy"}), 200


app.register_blueprint(userAPI)


if __name__ == "__main__":
    init_mongo(app)

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
