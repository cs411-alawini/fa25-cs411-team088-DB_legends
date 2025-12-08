import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from .config import Config
from .extensions import bcrypt, jwt
from .db import run_sql_script


def create_app() -> Flask:
    # Load env from backend/.env to work when running from project root
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)
    app = Flask(__name__)
    app.config.from_object(Config)

    # Extensions (bcrypt, jwt)
    bcrypt.init_app(app)
    jwt.init_app(app)

    # CORS
    origins_env = app.config.get("CORS_ORIGINS", "*")
    if isinstance(origins_env, str) and origins_env != "*":
        origins = [o.strip() for o in origins_env.split(",") if o.strip()]
    else:
        origins = origins_env
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": origins,
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                "allow_headers": ["Authorization", "Content-Type"],
                "expose_headers": ["Authorization"],
            }
        },
    )

    # Register API blueprints
    from .api.auth import bp as auth_bp
    from .api.accounts import bp as accounts_bp
    from .api.market import bp as market_bp
    from .api.news import bp as news_bp
    from .api.transactions import bp as tx_bp
    from .api.metrics import bp as metrics_bp
    from .api.watchlist import bp as watchlist_bp
    from .api.exports import bp as exports_bp
    from .api.groups import bp as groups_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(accounts_bp, url_prefix="/api/accounts")
    app.register_blueprint(market_bp, url_prefix="/api/market")
    app.register_blueprint(news_bp, url_prefix="/api/news")
    app.register_blueprint(tx_bp, url_prefix="/api")
    app.register_blueprint(metrics_bp, url_prefix="/api/metrics")
    app.register_blueprint(watchlist_bp, url_prefix="/api/watchlist")
    app.register_blueprint(exports_bp, url_prefix="/api/exports")
    app.register_blueprint(groups_bp, url_prefix="/api/groups")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    # CLI helpers
    @app.cli.command("create-db")
    def create_db():
        """Create all core tables using raw SQL."""
        sql_path = os.path.join(os.path.dirname(__file__), "db", "schema_tables.sql")
        if not os.path.exists(sql_path):
            print("schema_tables.sql not found")
            return
        with open(sql_path, "r", encoding="utf-8") as f:
            run_sql_script(f.read())
        print("Created tables.")

    @app.cli.command("apply-schema")
    def apply_schema():
        """Apply views, triggers, and functions."""
        sql_path = os.path.join(os.path.dirname(__file__), "db", "schema.sql")
        if not os.path.exists(sql_path):
            print("schema.sql not found")
            return
        with open(sql_path, "r", encoding="utf-8") as f:
            run_sql_script(f.read())
        print("Applied schema.")

    @app.cli.command("seed")
    def seed():
        from .db_seed import run_seed

        run_seed()
        print("Seed completed.")

    return app


app = create_app()
