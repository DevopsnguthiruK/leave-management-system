from . import db
from .leave import LeaveType
from .department import Department
from datetime import datetime
from flask_login import UserMixin

class User(UserMixin, db.Model):
    __tablename__= 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    role = db.Column(db.String(20), nullable=False)  # admin, approver, employee
    gender = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    department = db.relationship('Department', back_populates='users')
    leave_requests = db.relationship('LeaveRequest', foreign_keys='LeaveRequest.user_id', backref='user')
    approved_requests = db.relationship('LeaveRequest', foreign_keys='LeaveRequest.approver_id', backref='approver')
    leave_balances = db.relationship('LeaveBalance', backref='user')
    
    def get_id(self):
        return str(self.id)
    
class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    duration = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    leave_type = db.relationship('LeaveType', backref='leave_requests')

class LeaveBalance(db.Model):
    __tablename__ = 'leave_balances'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    leave_type_id = db.Column(db.Integer, db.ForeignKey('leave_types.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    total_days = db.Column(db.Integer, nullable=False)
    used_days = db.Column(db.Integer, default=0)
    remaining_days = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    leave_type = db.relationship('LeaveType', backref='leave_balances')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'leave_type_id', 'year', name='unique_leave_balance'),
    )

class RejectionReason(db.Model):
    __tablename__ = 'rejection_reasons'
    
    id = db.Column(db.Integer, primary_key=True)
    leave_request_id = db.Column(db.Integer, db.ForeignKey('leave_requests.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    rejected_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add relationship to LeaveRequest model
    leave_request = db.relationship('LeaveRequest', backref='rejection_reason', uselist=False)
