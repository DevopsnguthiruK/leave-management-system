# run.py
from app import create_app
from app.models import db
from werkzeug.security import generate_password_hash
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = create_app()

def init_db():
    """Initialize the database with some sample data."""
    try:
        with app.app_context():
            # Import models here
            from app.models.user import User
            from app.models.department import Department
            from app.models.leave import LeaveType
            
    except Exception as e:
        print(f"Error initializing database: {str(e)}")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)