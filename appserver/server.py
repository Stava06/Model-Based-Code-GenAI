from flask import Blueprint, Flask, jsonify


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return jsonify({"service": "appserver", "message": "ok"})

    @app.get("/health")
    def health():
        return jsonify({"status": "healthy"}), 200

    api = Blueprint("api", __name__, url_prefix="/api")

    @api.get("/hello")
    def hello():
        return jsonify({"hello": "world"})

    app.register_blueprint(api)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
