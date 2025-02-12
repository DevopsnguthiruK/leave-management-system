from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
 
from .user import User, LeaveRequest, LeaveBalance
from .department import Department
from .leave import LeaveType
from .notifications import Notification
