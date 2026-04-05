"""Flask Blueprints for Star Office UI feature modules."""

from flask import Flask


def register_blueprints(app: Flask):
    """Register all feature blueprints with the Flask app."""
    from blueprints.departments import departments_bp
    from blueprints.tasks import tasks_bp
    from blueprints.security import security_bp
    from blueprints.prompt_guard import prompt_guard_bp
    from blueprints.cost_dashboard import cost_dashboard_bp
    from blueprints.avatar import avatar_bp
    from blueprints.workspace_export import workspace_export_bp
    from blueprints.office_layout import office_layout_bp

    app.register_blueprint(departments_bp, url_prefix="/api")
    app.register_blueprint(tasks_bp, url_prefix="/api")
    app.register_blueprint(security_bp, url_prefix="/api")
    app.register_blueprint(prompt_guard_bp, url_prefix="/api")
    app.register_blueprint(cost_dashboard_bp, url_prefix="/api")
    app.register_blueprint(avatar_bp, url_prefix="/api")
    app.register_blueprint(workspace_export_bp, url_prefix="/api")
    app.register_blueprint(office_layout_bp, url_prefix="/api")
