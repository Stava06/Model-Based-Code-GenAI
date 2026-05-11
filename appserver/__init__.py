from flask import Flask, jsonify

from .api.users import userAPI


app = Flask(__name__)

@app.get("/")
def index():
    return jsonify({"service": "appserver", "message": "ok"})

@app.get("/health")
def health():
    return jsonify({"status": "healthy"}), 200

# Register blueprints
app.register_blueprint(userAPI)

app.run(host="0.0.0.0", port=5000, debug=True)