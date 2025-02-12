from flask import Blueprint, jsonify, request, render_template, redirect, url_for, flash, session
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash
from datetime import datetime
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.models import db, User, Department, LeaveType, LeaveBalance, LeaveRequest
from app.utils.decorators import admin_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField
from wtforms.validators import DataRequired, Email, Length
from app.models.holiday import Holiday
from app.models.user import RejectionReason

admin_bp = Blueprint('admin', __name__)
 
class UserCreationForm(FlaskForm):
    name = StringField('Name', validators=[
        DataRequired(message="Name is required"),
        Length(min=2, max=50, message="Name must be between 2 and 50 characters")
    ])
    email = StringField('Email', validators=[
        DataRequired(message="Email is required"),
        Email(message="Invalid email address")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=8, message="Password must be at least 8 characters long")
    ])
    department_id = SelectField('Department', coerce=int, validators=[
        DataRequired(message="Department selection is required")
    ])
    role = SelectField('Role', choices=[
        ('employee', 'Employee'),
        ('approver', 'Approver'),
        ('admin', 'Admin')
    ], validators=[DataRequired(message="Role selection is required")])
    gender = SelectField('Gender', choices=[
        ('male', 'Male'),
        ('female', 'Female')
    ], validators=[DataRequired(message="Gender selection is required")])

    class Meta:
        csrf = False  


@admin_bp.route('/dashboard')
@jwt_required()
@admin_required
def dashboard():
    try:
        departments = Department.query.all()
        department_stats = []
        
        for dept in departments:
            # Get total count of employees in department
            employee_count = User.query.filter_by(department_id=dept.id).count()
            
            department_stats.append({
                'id': dept.id,
                'name': dept.name,
                'code': dept.code,
                'employee_count': employee_count
            })
        
        # Get total number of employees
        active_users = User.query.count()
        
        # Get pending Leave requests count
        pending_requests = LeaveRequest.query.filter_by(status='pending').count()

        pending_leave_requests = LeaveRequest.query.filter_by(status='pending').all()

        return render_template('admin/dashboard.html',
                             departments=department_stats,
                             active_users=active_users,
                             departments_count=len(departments),
                             pending_requests=pending_requests,
                             pending_leave_requests=pending_leave_requests)
    except SQLAlchemyError as e:
        flash(f'Database error: {str(e)}', 'error')
        return redirect(url_for('main.index'))

        
@admin_bp.route('/users/create', methods=['GET', 'POST'])  
@jwt_required()
@admin_required
def create_user():
    try: 
        departments = Department.query.all()
        
        if request.method == 'GET':
            form = UserCreationForm()
            form.department_id.choices = [(d.id, d.name) for d in departments]
            return render_template('admin/create_user.html', form=form)

        if request.method == 'POST':
            json_data = request.get_json()
            if not json_data:
                return jsonify({'message': 'No input data provided'}), 400

            # Initialize form with JSON data
            form = UserCreationForm(data=json_data)
            form.department_id.choices = [(d.id, d.name) for d in departments]
                
            if not form.validate():
                return jsonify({
                    'message': 'Validation error',
                    'errors': form.errors
                }), 422
            
            # Check if user already exists
            existing_user = User.query.filter_by(email=form.email.data).first()
            if existing_user:
                return jsonify({'message': 'Email already exists'}), 400

            # Create new user
            new_user = User(
                name=form.name.data,
                email=form.email.data,
                password=generate_password_hash(form.password.data),
                department_id=form.department_id.data,
                role=form.role.data,
                gender=form.gender.data
            )

            db.session.add(new_user)
            db.session.flush()

            # Create initial leave balances
            leave_types = LeaveType.query.all()
            for lt in leave_types:
                if lt.gender_specific and lt.gender_specific != new_user.gender:
                    continue

                balance = LeaveBalance(
                    user_id=new_user.id,
                    leave_type_id=lt.id,
                    year=datetime.now().year,
                    total_days=lt.days_allowed,
                    remaining_days=lt.days_allowed
                )
                db.session.add(balance)

            db.session.commit()
            return jsonify({'message': 'User created successfully'}), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'Database integrity error. Please check your input.'}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Unexpected error: {str(e)}'}), 500

@admin_bp.route('/departments')  
@jwt_required()
@admin_required
def manage_departments():
    try:
        departments = Department.query.all()
        return render_template('admin/departments.html', departments=departments)
    except SQLAlchemyError as e:
        flash(f'Error fetching departments: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@admin_bp.route('/roles')
@jwt_required()
@admin_required
def manage_roles():
    try:
        # Make sure to only get users with valid department relationships
        users = User.query.filter(User.department_id.isnot(None)).all()
        departments = Department.query.all()
        return render_template('admin/roles.html', users=users, departments=departments)
    except SQLAlchemyError as e:
        flash(f'Error fetching users: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@jwt_required()
@admin_required
def update_user_role(user_id):
    try:
        data = request.get_json()  # Changed from form to json
        if not data or 'role' not in data:
            return jsonify({'message': 'Role data is required'}), 400

        user = User.query.get_or_404(user_id)
        new_role = data['role']

        if new_role not in ['employee', 'approver', 'admin']:
            return jsonify({'message': 'Invalid role'}), 400
        
        user.role = new_role
        db.session.commit()
        return jsonify({'message': 'Role updated successfully'})
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating role: {str(e)}'}), 500

@admin_bp.route('/users/<int:user_id>/delete', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_user(user_id):
    try:
        # Find the user to delete
        user = User.query.get_or_404(user_id)
        
        # Prevent deleting the last admin
        admin_count = User.query.filter_by(role='admin').count()
        if user.role == 'admin' and admin_count <= 1:
            return jsonify({'message': 'Cannot delete the last admin user'}), 400
        
        # Delete associated leave balances first
        LeaveBalance.query.filter_by(user_id=user_id).delete()
        
        # Delete the user
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'message': 'User deleted successfully'}), 200
    
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Error deleting user: {str(e)}'}), 500
      
@admin_bp.route('/departments/<int:dept_id>', methods=['GET'])
@jwt_required()
@admin_required
def get_department_users(dept_id):
    try:
        users = User.query.filter_by(department_id=dept_id).all()
        return jsonify({
            'users': [{'id': user.id, 'name': user.name, 'role': user.role}
                    for user in users]
        })
    except SQLAlchemyError as e:
        return jsonify({'message': f'Error fetching users: {str(e)}'}), 500

@admin_bp.route('/departments/<int:dept_id>/delete', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_department(dept_id):
    try:
        # Find the department to delete
        department = Department.query.get_or_404(dept_id)
        
        # Check if the department has any employees
        employee_count = User.query.filter_by(department_id=dept_id).count()
        
        # Prevent deleting a department with employees
        if employee_count > 0:
            return jsonify({
                'message': f'Cannot delete department. {employee_count} employee(s) are currently assigned to this department.'
            }), 400
        
        # Delete the department
        db.session.delete(department)
        db.session.commit()
        
        return jsonify({'message': 'Department deleted successfully'}), 200
    
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Error deleting department: {str(e)}'}), 500

@admin_bp.route('/departments/create', methods=['POST'])
@jwt_required()
@admin_required
def create_department():
    try:
        data = request.get_json()
        name = data.get('name')
        code = data.get('code')
        
        if not name or not code:
            return jsonify({'message': 'Department name and code are required'}), 400
        
        # Check for existing department
        existing_dept = Department.query.filter(
            (Department.name == name) | (Department.code == code)
        ).first()
        
        if existing_dept:
            return jsonify({'message': 'Department already exists'}), 400
            
        new_department = Department(
            name=name,
            code=code
        )
        db.session.add(new_department)
        db.session.commit()

        return jsonify({
            'message': 'Department created successfully',
            'department': {
                'id': new_department.id,
                'name': new_department.name,
                'code': new_department.code,
                'employee_count': 0
            }
        })

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Error creating department: {str(e)}'}), 500

@admin_bp.route('/departments/<int:dept_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_department(dept_id):
    try:
        data = request.get_json()
        department = Department.query.get_or_404(dept_id)
        
        
        if 'name' in data:
            department.name = data['name']
        if 'code' in data:
            department.code = data['code']
        
        db.session.commit()

        return jsonify({
            'message': 'Department updated successfully',
            'department': {
                'id': department.id,
                'name': department.name,
                'code': department.code,
                'employee_count': len(department.users)
            }
        })
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating department: {str(e)}'}), 500

@admin_bp.route('/holidays')
@jwt_required()
@admin_required
def manage_holidays():
    try:
        # Get holidays for the current year and future
        current_year = datetime.now().year
        holidays = Holiday.query.filter(
            db.extract('year', Holiday.date) >= current_year
        ).order_by(Holiday.date).all()
        
        return render_template('admin/holidays.html', holidays=holidays)
    except SQLAlchemyError as e:
        flash(f'Error fetching holidays: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/holidays/create', methods=['GET', 'POST'])
@jwt_required()
@admin_required
def create_holiday():
    try:
        if request.method == 'POST':
            data = request.get_json()
            
            # Validate input
            if not data or not data.get('name') or not data.get('date'):
                return jsonify({'message': 'Name and date are required'}), 400
            
            # Parse date
            try:
                holiday_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'message': 'Invalid date format. Use YYYY-MM-DD'}), 400
            
            # Create new holiday
            new_holiday = Holiday(
                name=data['name'],
                date=holiday_date,
                description=data.get('description', ''),
                is_recurring=data.get('is_recurring', False)
            )
            
            db.session.add(new_holiday)
            db.session.commit()
            
            return jsonify({
                'message': 'Holiday created successfully',
                'holiday': new_holiday.to_dict()
            }), 201
        
    except IntegrityError:
        db.session.rollback()
        return jsonify({'message': 'Database integrity error'}), 400
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Database error: {str(e)}'}), 500

@admin_bp.route('/holidays/<int:holiday_id>/delete', methods=['DELETE'])
@jwt_required()
@admin_required
def delete_holiday(holiday_id):
    try:
        holiday = Holiday.query.get_or_404(holiday_id)
        
        db.session.delete(holiday)
        db.session.commit()
        
        return jsonify({'message': 'Holiday deleted successfully'}), 200
    
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Error deleting holiday: {str(e)}'}), 500  
    # Add this function to your admin.py file after the other route handlers

# Update admin.py - Modify the update_leave_request function
@admin_bp.route('/leave-requests/<int:request_id>/update', methods=['POST'])
@jwt_required()
@admin_required
def update_leave_request(request_id):
    try:
        leave_request = LeaveRequest.query.get_or_404(request_id)
        data = request.get_json()
        new_status = data.get('status')
        rejection_reason = data.get('rejectionReason')
        
        if not new_status or new_status not in ['approved', 'rejected']:
            return jsonify({'message': 'Invalid status provided'}), 400
            
        if new_status == 'rejected' and not rejection_reason:
            return jsonify({'message': 'Rejection reason is required'}), 400
        
        # Update the leave request
        leave_request.status = new_status
        leave_request.approver_id = get_jwt_identity()
        
        if new_status == 'rejected' and rejection_reason:
            # Create rejection reason record
            reason = RejectionReason(
                leave_request_id=request_id,
                reason=rejection_reason,
                rejected_by=get_jwt_identity()
            )
            db.session.add(reason)
        elif new_status == 'approved':
            # Update leave balance
            leave_balance = LeaveBalance.query.filter_by(
                user_id=leave_request.user_id,
                leave_type_id=leave_request.leave_type_id,
                year=datetime.now().year
            ).first()
            
            if leave_balance:
                if leave_balance.remaining_days >= leave_request.duration:
                    leave_balance.used_days += leave_request.duration
                    leave_balance.remaining_days -= leave_request.duration
                else:
                    return jsonify({'message': 'Insufficient leave balance'}), 400
        
        db.session.commit()
        return jsonify({'message': f'Leave request {new_status} successfully'}), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({'message': f'Error updating leave request: {str(e)}'}), 500