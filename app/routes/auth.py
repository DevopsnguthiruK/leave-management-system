from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, make_response
from flask_jwt_extended import create_access_token, set_access_cookies
from werkzeug.security import check_password_hash
from app.models import User
from flask_login import login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Email


auth_bp = Blueprint('auth', __name__)

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')

    class Meta:
        csrf = False

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    
    if request.method == 'POST':
        try:
            #checkk if request is JSON
            if request.is_json:
                data = request.get_json()
                email = data.get('email')
                password = data.get('password')
                remember = data.get('remember_me', False)
            else:
                if not form.validate():
                    # Log validation errors
                    print("Form validation failed:", form.errors)
                    for field, errors in form.errors.items():
                        for error in errors:
                            flash(f"{field}: {error}", 'error')
                    return render_template('auth/login.html', form=form), 422
                
                email = form.email.data
                password = form.password.data
                remember = form.remember_me.data

            user = User.query.filter_by(email=email).first()
            
            if not user or not check_password_hash(user.password, password):
                error_message = 'Invalid email or password'
                if request.is_json:
                    return {'message': error_message}, 401
                flash(error_message, 'error')
                return render_template('auth/login.html', form=form), 401
            
            # Login successful
            if user and check_password_hash(user.password, password):
                login_user(user, remember=remember)
                access_token = create_access_token(identity=str(user.id))
    

            # Redirect based on user role
            if user.role == 'admin':
                redirect_url = url_for('admin.dashboard')
            elif user.role == 'approver':
                redirect_url = url_for('approver.dashboard')
            else:
                redirect_url = url_for('employee.dashboard')
            
            response = make_response(
                jsonify({
                    'message': 'Login successful',
                    'access_token': access_token,
                    'redirect_url': redirect_url
                }) if request.is_json else redirect(redirect_url)
            )
        
            set_access_cookies(response, access_token)
            return response
                
        except Exception as e:
            print(f"Login error: {str(e)}")
            error_message = 'An unexpected error occurred. Please try again.'
            if request.is_json:
                return {'message': error_message}, 500
            flash(error_message, 'error')
            return render_template('auth/login.html', form=form), 500
                
    return render_template('auth/login.html', form=form)
    
@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login')) 
    

