from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, Notification, LeaveRequest
from app.models.user import RejectionReason
from sqlalchemy import desc
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('', methods=['GET'])
@jwt_required()
def get_notifications():
    try:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({'message': 'Invalid user token'}), 401
            
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Add debug logging
        print(f"Fetching notifications for user {user_id}, page {page}")
        
        notifications = Notification.query\
            .outerjoin(LeaveRequest, 
                      (Notification.reference_type == 'leave_request') & 
                      (Notification.reference_id == LeaveRequest.id))\
            .outerjoin(RejectionReason, LeaveRequest.id == RejectionReason.leave_request_id)\
            .filter(Notification.user_id == user_id)\
            .order_by(desc(Notification.created_at))\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        # Debug logging
        print(f"Found {len(notifications.items)} notifications")
        
        notifications_list = []
        for notif in notifications.items:
            leave_request = None
            rejection_reason = None
            
            if notif.reference_type == 'leave_request' and notif.reference_id:
                leave_request = LeaveRequest.query.get(notif.reference_id)
                if leave_request and leave_request.status == 'rejected':
                    rejection_reason = RejectionReason.query.filter_by(
                        leave_request_id=leave_request.id
                    ).first()
            
            notification_data = {
                'id': notif.id,
                'message': notif.message,
                'type': notif.notification_type,
                'is_read': notif.is_read,
                'created_at': notif.created_at.isoformat() if notif.created_at else None,
                'reference_type': notif.reference_type,
                'reference_id': notif.reference_id,
                'status': leave_request.status if leave_request else None,
                'rejection_reason': rejection_reason.reason if rejection_reason else None
            }
            notifications_list.append(notification_data)
        
        response = {
            'notifications': notifications_list,
            'total_pages': notifications.pages,
            'current_page': page,
            'total_items': notifications.total,
            'has_next': notifications.has_next,
            'has_prev': notifications.has_prev
        }
        
        return jsonify(response), 200

    except Exception as e:
        print(f"Error in get_notifications: {str(e)}")
        import traceback
        traceback.print_exc()  # Print full stack trace
        return jsonify({'message': f'Error fetching notifications: {str(e)}'}), 500

@notifications_bp.route('/mark-read', methods=['POST'])
@jwt_required()
def mark_notifications_read():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            data = {}
        
        # If specific notification IDs are provided, mark only those as read
        if 'notification_ids' in data and data['notification_ids']:
            notifications = Notification.query.filter(
                Notification.id.in_(data['notification_ids']),
                Notification.user_id == user_id
            ).all()
            for notification in notifications:
                notification.is_read = True
        else:
            # Mark all user's notifications as read
            Notification.query.filter_by(user_id=user_id).update({'is_read': True})
        
        db.session.commit()
        return jsonify({'message': 'Notifications marked as read'}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error in mark_notifications_read: {str(e)}")
        return jsonify({'message': f'Error marking notifications as read: {str(e)}'}), 500