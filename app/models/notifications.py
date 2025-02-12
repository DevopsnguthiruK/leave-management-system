from datetime import datetime
from . import db

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)  # 'success', 'error', 'info'
    reference_id = db.Column(db.Integer, nullable=True)  # To store leave_request_id
    reference_type = db.Column(db.String(50), nullable=True)  # To identify the type of reference (e.g., 'leave_request')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Notification {self.id}>'

def create_leave_notification(leave_request, status_change=False):
    """
    Create a notification for a leave request based on its status
    
    Args:
        leave_request: LeaveRequest object
        status_change: Boolean indicating if this is a status change notification
    """
    if leave_request.status == 'approved':
        message = (
            f"Leave request {leave_request.id} has been approved.\n"
            f"Type: {leave_request.leave_type.name}\n"
            f"Duration: {leave_request.duration} days\n"
            f"Period: {leave_request.start_date.strftime('%Y-%m-%d')} to {leave_request.end_date.strftime('%Y-%m-%d')}"
        )
        notification_type = 'success'
    
    elif leave_request.status == 'rejected':
        rejection_info = leave_request.rejection_reason
        reason = rejection_info.reason if rejection_info else "No reason provided"
        
        message = (
            f"Leave request {leave_request.id} has been rejected.\n"
            f"Type: {leave_request.leave_type.name}\n"
            f"Duration: {leave_request.duration} days\n"
            f"Period: {leave_request.start_date.strftime('%Y-%m-%d')} to {leave_request.end_date.strftime('%Y-%m-%d')}\n"
            f"Reason for rejection: {reason}"
        )
        notification_type = 'error'
    
    elif leave_request.status == 'pending' and not status_change:
        message = (
            f"New leave request submitted.\n"
            f"Type: {leave_request.leave_type.name}\n"
            f"Duration: {leave_request.duration} days\n"
            f"Period: {leave_request.start_date.strftime('%Y-%m-%d')} to {leave_request.end_date.strftime('%Y-%m-%d')}"
        )
        notification_type = 'info'
    
    else:
        return None

    notification = Notification(
        user_id=leave_request.user_id,
        message=message,
        notification_type=notification_type,
        reference_id=leave_request.id,
        reference_type='leave_request'
    )
    
    db.session.add(notification)
    db.session.commit()
    return notification

