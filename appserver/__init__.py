from flask import Flask, jsonify
from pymongo.errors import PyMongoError

from .config import CONFIG
from .extensions import init_mongo
from .api.users import userAPI


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

# Register blueprints
app.register_blueprint(userAPI)

app.run(host="0.0.0.0", port=5000, debug=True)