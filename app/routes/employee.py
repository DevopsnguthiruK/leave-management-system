from flask import Blueprint, request, jsonify, flash, redirect, url_for, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import db, LeaveRequest, LeaveBalance, LeaveType
from app.models.notifications import Notification, create_leave_notification
from datetime import datetime, timedelta
import calendar
import holidays
from app.models.user import RejectionReason
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

employee_bp = Blueprint('employee', __name__, )


def process_leave_request(leave_request):
    """
    Process a leave request and update balances accordingly
    Sends detailed notifications for both approved and rejected requests
    """
    try:
        # Get the current balance
        balance = LeaveBalance.query.filter_by(
            user_id=leave_request.user_id,
            leave_type_id=leave_request.leave_type_id,
            year=datetime.now().year
        ).first()
        
        if not balance:
            raise ValueError('Leave balance not found')
            
        if leave_request.status == 'approved':
            # Only deduct the balance when the request is approved
            if balance.remaining_days < leave_request.duration:
                raise ValueError('Insufficient leave balance')
                
            balance.remaining_days -= leave_request.duration
            balance.used_days += leave_request.duration
            
        # Create notification for status change
        create_leave_notification(leave_request, status_change=True)
            
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        raise e

@employee_bp.route('/dashboard')
@jwt_required()
def dashboard():
    user_id = get_jwt_identity()
    current_date = datetime.now()
    
    # Get the displayed month (default to current month)
    displayed_month = request.args.get('month', current_date.strftime('%Y-%m'))
    year, month = map(int, displayed_month.split('-'))
    
    # Get calendar data
    cal = calendar.monthcalendar(year, month)
    ke_holidays = holidays.KE(years=year)
    
    # Get user's leave requests for the month
    leave_requests = LeaveRequest.query.filter_by(user_id=user_id).all()
    
    # Get leave dates for highlighting on calendar
    leave_dates = set()
    for req in leave_requests:
        if req.status == 'approved':
            current = req.start_date
            while current <= req.end_date:
                leave_dates.add(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)
    
    # Format calendar data for template
    calendar_weeks = []
    for week in cal:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append({'day': None})
                continue
                
            date = datetime(year, month, day).date()
            date_str = date.strftime('%Y-%m-%d')
            
            day_data = {
                'day': day,
                'is_weekend': date.weekday() >= 5,
                'is_holiday': date in ke_holidays,
                'holiday_name': ke_holidays.get(date),
                'has_leave': date_str in leave_dates,
                'is_past': date < current_date.date(),
                'is_today': date == current_date.date()
            }
            week_data.append(day_data)
        calendar_weeks.append(week_data)
    
   # Get leave balances
    leave_balances = db.session.query(LeaveBalance, LeaveType).join(LeaveType).filter(
        LeaveBalance.user_id == user_id,
        LeaveBalance.year == current_date.year
    ).all()
    
    # Get leave types for the request form
    leave_types = LeaveType.query.all()
    
    # Get user's notifications
    notifications = Notification.query.filter_by(
        user_id=user_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('employee/dashboard.html',
        current_month=displayed_month,
        calendar_weeks=calendar_weeks,
        leave_requests=leave_requests,
        leave_balances=leave_balances,
        leave_types=leave_types,
        notifications=notifications
    )
@employee_bp.route('/leave-request', methods=['POST'])
@jwt_required()
def submit_leave_request():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'message': 'No input data provided'}), 400

        # Validate required fields
        required_fields = ['start_date', 'end_date', 'leave_type_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'message': f'{field} is required'}), 400

        user_id = get_jwt_identity()
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()

        # Validate date range
        if start_date > end_date:
            return jsonify({'message': 'Start date must be before or equal to end date'}), 400

        # Validate that dates are in the future
        if start_date < datetime.now().date():
            return jsonify({'message': 'Leave start date must be in the future'}), 400

        # Find the leave type
        leave_type = LeaveType.query.get(data['leave_type_id'])
        if not leave_type:
            return jsonify({'message': 'Invalid leave type'}), 400

        # Calculate leave duration using the leave type's method
        leave_duration = leave_type.calculate_leave_request_duration(start_date, end_date)

        # Check leave balance
        balance = LeaveBalance.query.filter_by(
            user_id=user_id,
            leave_type_id=data['leave_type_id'],
            year=datetime.now().year
        ).first()

        # Validate leave balance
        if not balance or balance.remaining_days < leave_duration:
            return jsonify({'message': 'Insufficient leave balance'}), 400

        # Create leave request
        leave_request = LeaveRequest(
            user_id=user_id,
            leave_type_id=data['leave_type_id'],
            start_date=start_date,
            end_date=end_date,
            duration=leave_duration,
            reason=data.get('reason', ''),
            status='pending'  # Explicitly set status to pending
        )

        db.session.add(leave_request)
        db.session.flush()

        # Create notification for new request
        create_leave_notification(leave_request)

        db.session.commit()

        return jsonify({
            'message': 'Leave request submitted successfully',
            'duration': leave_duration
        }), 201

    except ValueError as ve:
        return jsonify({'message': f'Invalid date format: {str(ve)}'}), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'Database integrity error. Please check your input.'}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Unexpected error: {str(e)}'}), 500

    
@employee_bp.route('/leave-requests', methods=['GET'])
@jwt_required()
def get_my_requests():
    user_id = get_jwt_identity()
    requests = LeaveRequest.query.filter_by(user_id=user_id).all()
    
    return jsonify([{
        'id': req.id,
        'leave_type': req.leave_type,  
        'start_date': req.start_date.strftime('%Y-%m-%d'),
        'end_date': req.end_date.strftime('%Y-%m-%d'),
        'duration': req.duration,
        'status': req.status,
        'reason': req.reason,
        'rejection_reason': req.rejection_reason
    } for req in requests]), 200

    