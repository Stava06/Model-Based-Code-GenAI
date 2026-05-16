import os

from flask import Flask, jsonify
from pymongo.errors import PyMongoError

from api.users import userAPI
from config import CONFIG
from extensions import init_mongo

app = Flask(__name__)

app.config["MONGODB_URI"] = CONFIG["database"]["uri"]

init_mongo(app)


@app.get("/")
def index():
    check_db = False
    coll = app.extensions.get("users_collection")
    if coll is not None:
        try:
            coll.database.client.admin.command("ping")
            check_db = True
        except PyMongoError:
            check_db = False
    return jsonify(
        {"service": "appserver", "message": "ok", "db_connected": "yes" if check_db else "no"}
    )


@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200


app.register_blueprint(userAPI)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
