from flask import Blueprint
from .auth import auth_bp
from .admin import admin_bp
from .approver import approver_bp
from .employee import employee_bp
from .notifications import notifications_bp


# Initialize blueprints
def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(approver_bp, url_prefix='/api/approver')
    app.register_blueprint(employee_bp, url_prefix='/api/employee')
    app.register_blueprint(notifications_bp)