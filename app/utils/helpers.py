from datetime import datetime, timedelta
import random
import string
from flask import current_app
import holidays
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def calculate_leave_duration(start_date, end_date):
    """Calculate working days between two dates, excluding weekends and holidays."""
    ke_holidays = holidays.KE()
    duration = 0
    current_date = start_date

    while current_date <= end_date:
        # Skip weekends and holidays
        if current_date.weekday() < 5 and current_date not in ke_holidays:
            duration += 1
        current_date += timedelta(days=1)
    
    return

def validate_date_range(start_date, end_date):
    """Validate if the date range is valid."""
    if not isinstance(start_date, datetime):
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    if not isinstance(end_date, datetime):
        end_date = datetime.strptime(end_date, '%Y-%m-%d')


    # Check if start date is in the past
    if start_date.date() < datetime.now().date():
        return False, "Start date cannot be in the past"
    
    # Check if end date is before start date
    if end_date < start_date:
        return False, "End date must be after start date"
    
    return True, "Date range is valid"

def send_notification(recipient_email, subject, body):
    """send email notification."""
    try:
        msg = MIMEMultipart()
        msg['From'] = current_app.config['MAIL_USERNAME']
        msg['To'] = recipient_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'])
        server.starttls()
        server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()

        return True, "Notification sent successfully"
    except Exception as e:
        return False, str(e)
    
def format_date(date_obj):
    """"Format date object to string."""
    if isinstance(date_obj, str):
        return date_obj
    return date_obj.strftime('%Y-%m-%d')

def generate_password(length=12):
    """Generate a random password."""
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for i in range(length))

def create_notification(user_id, message, notification_type='info'):
    """Create a new notification for a user."""
    notification = Notification(
        user_id=user_id,
        message=message,
        notification_type=notification_type
    )
    db.session.add(notification)
    db.session.commit()
    return notification

