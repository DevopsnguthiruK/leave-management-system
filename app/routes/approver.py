from flask import Blueprint, jsonify, request, render_template, redirect, url_for, flash, send_file, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from app.models import db, User, Department, LeaveType, LeaveBalance, LeaveRequest
from app.models.user import RejectionReason
from app.utils.decorators import approver_required
import pandas as pd
from io import BytesIO
import pdfkit
import platform

approver_bp = Blueprint('approver', __name__)

if platform.system() == 'Windows':
    path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
else:
    # Common path for Linux installations
    path_wkhtmltopdf = '/usr/bin/wkhtmltopdf'


config = pdfkit.configuration(wkhtmltopdf='C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')

# Configure PDF options
pdf_options = {
                'page-size': 'A4',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': 'UTF-8',
                'enable-local-file-access': True,  
                'footer-center': '[page] of [topage]',
                'footer-font-size': '9',
                'footer-spacing': '5'
            }           

@approver_bp.route('/dashboard')
@jwt_required()
@approver_required
def dashboard():
    try:
        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        
        # Get ALL employees
        employees = User.query.filter(User.role == 'employee').all()
        employee_count = len(employees)
        
        # Get ALL pending leave requests (not just department specific)
        pending_requests = LeaveRequest.query.filter_by(status='pending').all()
        
        # Get all departments count
        departments_count = Department.query.count()
        
        # Get leave types
        leave_types = LeaveType.query.all()
        
        # Initialize employee balances with proper error handling
        employee_balances = []
        current_year = datetime.now().year
        
        for employee in employees:
            # Get all leave balances for this employee in the current year
            leave_balances = LeaveBalance.query.filter_by(
                user_id=employee.id,
                year=current_year
            ).all()
            
            # Create a dictionary to store leave balances by leave type
            balance_dict = {balance.leave_type_id: balance for balance in leave_balances}
            
            balances = {}
            for leave_type in leave_types:
                balance = balance_dict.get(leave_type.id)
                
                # Handle gender-specific leave types
                if (leave_type.name.lower() == 'maternity leave' and employee.gender.lower() != 'female') or \
                   (leave_type.name.lower() == 'paternity leave' and employee.gender.lower() != 'male'):
                    balances[leave_type.name] = 'N/A'
                else:
                    if balance:
                        balances[leave_type.name] = balance.remaining_days
                    else:
                        balances[leave_type.name] = 0
            
            employee_balances.append({
                'employee': employee,
                'balances': balances
            })

        return render_template('approver/dashboard.html',
                             current_user=current_user,
                             employees=employee_balances,
                             leave_types=leave_types,
                             employee_count=employee_count,
                             departments_count=departments_count,
                             pending_requests=len(pending_requests),
                             department_requests=pending_requests)
                             
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Database error: {str(e)}', 'error')
        return redirect(url_for('index'))

@approver_bp.route('/request/<int:request_id>', methods=['PUT'])
@jwt_required()
@approver_required
def update_leave_request(request_id):
    try:
        leave_request = LeaveRequest.query.get_or_404(request_id)
        data = request.get_json()
        new_status = data.get('status')
        rejection_reason = data.get('rejection_reason')
        
        if not new_status or new_status not in ['approved', 'rejected']:
            return jsonify({'message': 'Invalid status provided'}), 400
            
        if new_status == 'rejected' and not rejection_reason:
            return jsonify({'message': 'Rejection reason is required'}), 400
        
        # Update the leave request
        leave_request.status = new_status
        leave_request.approver_id = get_jwt_identity()
        leave_request.updated_at = datetime.now()
        
        if new_status == 'rejected' and rejection_reason:
            # Create rejection reason record
            reason = RejectionReason(
                leave_request_id=request_id,
                reason=rejection_reason,
                rejected_by=get_jwt_identity(),
                created_at=datetime.now()
            )
            db.session.add(reason)
        elif new_status == 'approved':
            # Update leave balance
            leave_balance = LeaveBalance.query.filter_by(
                user_id=leave_request.user_id,
                leave_type_id=leave_request.leave_type_id,
                year=datetime.now().year
            ).first()
            
            if not leave_balance:
                return jsonify({'message': 'Leave balance not found'}), 400
                
            if leave_balance.remaining_days < leave_request.duration:
                return jsonify({'message': 'Insufficient leave balance'}), 400
                
            leave_balance.used_days += leave_request.duration
            leave_balance.remaining_days -= leave_request.duration
            leave_balance.updated_at = datetime.now()
        
        db.session.commit()
        return jsonify({
            'message': f'Leave request {new_status} successfully',
            'status': 'success'
        }), 200
        
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error in update_leave_request: {str(e)}")
        return jsonify({
            'message': 'An error occurred while updating the leave request',
            'error': str(e)
        }), 500
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error in update_leave_request: {str(e)}")
        return jsonify({
            'message': 'An unexpected error occurred',
            'error': str(e)
        }), 500
    
@approver_bp.route('/reports/leave-requests')
@jwt_required()
@approver_required
def leave_requests_report():
    try:
        current_user = User.query.get(get_jwt_identity())
        
        # Get filter parameters
        leave_type = request.args.get('leave_type')
        status = request.args.get('status')
        
        # Base query - removed department filter to show all requests
        query = LeaveRequest.query.join(
            User,
            LeaveRequest.user_id == User.id
        )
        
        # Apply filters
        if leave_type:
            query = query.filter(LeaveRequest.leave_type_id == leave_type)
        if status:
            query = query.filter(LeaveRequest.status == status)
            
        requests = query.all()
        
        # Format for PDF if requested
        if request.args.get('format') == 'pdf':
            data = [{
                'Employee': req.user.name,
                'Leave Type': req.leave_type.name,
                'Start Date': req.start_date.strftime('%Y-%m-%d'),
                'End Date': req.end_date.strftime('%Y-%m-%d'),
                'Duration': f"{req.duration} days",
                'Status': req.status.capitalize(),
                'Department': req.user.department.name  
            } for req in requests]
            
            df = pd.DataFrame(data)
            
            html = render_template('reports/leave_requests_pdf.html', 
                                 requests=data,
                                 department="All Departments",  
                                 generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            pdf = pdfkit.from_string(html, False, configuration=config, options=pdf_options)
            
            response = send_file(
                BytesIO(pdf),
                download_name=f'leave_requests_report_{datetime.now().strftime("%Y%m%d")}.pdf',
                mimetype='application/pdf'
            )
            
            return response
            
        # Return regular template
        return render_template('approver/leave_requests_report.html',
                             requests=requests,
                             current_user=current_user)
        
    except SQLAlchemyError as e:
        return jsonify({'message': f'Error generating report: {str(e)}'}), 500

@approver_bp.route('/reports/staff')
@jwt_required()
@approver_required
def staff_report():
    try:
        current_user = User.query.get(get_jwt_identity())
        
        # Get only employees (filter out admin and approver roles)
        employees = User.query.filter(User.role == 'employee').all()
        
        # Format for PDF if requested
        if request.args.get('format') == 'pdf':
            # Convert the data to a format suitable for PDF
            data = [{
                'Name': emp.name,
                'Email': emp.email,
                'Role': emp.role,
                'Gender': emp.gender,
                'Join Date': emp.created_at.strftime('%Y-%m-%d')
            } for emp in employees]
            
            try:
                # Create PDF using the template
                html = render_template('reports/staff_pdf.html',
                                     employees=data,
                                     department="All Departments",
                                     generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                
                pdf = pdfkit.from_string(html, False, configuration=config, options=pdf_options)
                
                # Create response
                response = send_file(
                    BytesIO(pdf),
                    download_name=f'staff_report_{datetime.now().strftime("%Y%m%d")}.pdf',
                    mimetype='application/pdf'
                )
                
                return response
                
            except IOError as e:
                current_app.logger.error(f"PDF generation error: {str(e)}")
                flash("Error generating PDF report. Please try again.", "error")
                return redirect(url_for('approver.staff_report'))
            
        # Return regular template
        return render_template('approver/staff_report.html',
                             employees=employees,
                             current_user=current_user)
        
    except SQLAlchemyError as e:
        current_app.logger.error(f"Database error: {str(e)}")
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('approver.dashboard'))

@approver_bp.route('/reports/leave-utilization')
@jwt_required()
@approver_required
def leave_utilization_report():
    try:
        current_user = User.query.get(get_jwt_identity())
        
        # Get all employees regardless of department
        employees = User.query.filter(User.role == 'employee').all()
        leave_types = LeaveType.query.all()
        
        utilization_data = []
        for employee in employees:
            employee_data = {
                'employee': employee.name,
                'department': employee.department.name,  # Added department name for reference
                'utilization': {}
            }
            
            for leave_type in leave_types:
                balance = LeaveBalance.query.filter_by(
                    user_id=employee.id,
                    leave_type_id=leave_type.id,
                    year=datetime.now().year
                ).first()
                
                if balance:
                    utilization = (balance.used_days / balance.total_days * 100) if balance.total_days > 0 else 0
                    employee_data['utilization'][leave_type.name] = {
                        'total': balance.total_days,
                        'used': balance.used_days,
                        'remaining': balance.remaining_days,
                        'utilization_percentage': round(utilization, 2)
                    }
                    
            utilization_data.append(employee_data)  
        # Format for PDF if requested
        if request.args.get('format') == 'pdf':
            # Create PDF using the template
            html = render_template('reports/utilization_pdf.html',
                                 utilization=utilization_data,
                                 leave_types=leave_types,
                                 department="All Departments",  # Updated to show all departments
                                 generated_date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            pdf = pdfkit.from_string(html, False, configuration=config, options=pdf_options)
            
            # Create response
            response = send_file(
                BytesIO(pdf),
                download_name=f'leave_utilization_report_{datetime.now().strftime("%Y%m%d")}.pdf',
                mimetype='application/pdf'
            )
            
            return response
            
        # Return regular template
        return render_template('approver/utilization_report.html',
                             utilization=utilization_data,
                             leave_types=leave_types,
                             current_user=current_user)
        
    except SQLAlchemyError as e:
        return jsonify({'message': f'Error generating report: {str(e)}'}), 500
