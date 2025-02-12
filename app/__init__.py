from flask import Flask, redirect, url_for
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_login import LoginManager
from .models import db
from .config import Config


login_manager = LoginManager()
jwt = JWTManager()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
   
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)
    CORS(app)
    
    login_manager.login_view = 'auth.login'

    with app.app_context():
        # Import models here to avoid circular imports
        from .models.user import User, LeaveRequest, LeaveBalance, RejectionReason
        from .models.leave import LeaveType
        from .models.department import Department
        from .models.notifications import Notification
    
        
        # Import and register blueprints
        from .routes import auth_bp, admin_bp, approver_bp, employee_bp, notifications_bp
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(admin_bp, url_prefix='/admin')
        app.register_blueprint(approver_bp, url_prefix='/approver')
        app.register_blueprint(employee_bp, url_prefix='/employee')
        app.register_blueprint(notifications_bp)
        
        @app.route('/')
        def index():
            return redirect(url_for('auth.login'))
        
        @login_manager.user_loader
        def load_user(user_id):
            return User.query.get(int(user_id))
        
        # Create tables
        db.create_all()
    
    return app