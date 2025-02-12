from datetime import datetime, timedelta
from . import db
import holidays

def calculate_leave_duration(start_date, end_date, year=None):
    """
    Calculate leave duration excluding weekends and holidays
    
    Args:
        start_date (date): Start of leave period
        end_date (date): End of leave period
        year (int, optional): Year for holiday calculation. Defaults to start_date's year.
    
    Returns:
        int: Number of working days in the leave period
    """
    if year is None:
        year = start_date.year
    
    # Use Kenyan holidays (assuming this is a Kenyan system based on previous code)
    ke_holidays = holidays.KE(years=year)
    
    working_days = 0
    current_date = start_date
    
    while current_date <= end_date:
        # Check if it's a weekday (Monday=0, Friday=4)
        is_weekday = current_date.weekday() < 5
        
        # Check if it's not a holiday
        is_not_holiday = current_date not in ke_holidays
        
        # Count the day if it's a weekday and not a holiday
        if is_weekday and is_not_holiday:
            working_days += 1
        
        current_date += timedelta(days=1)
    
    return working_days

class LeaveType(db.Model):
    __tablename__ = 'leave_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    days_allowed = db.Column(db.Integer, nullable=False)
    gender_specific = db.Column(db.String(10), nullable=True)

    def calculate_leave_request_duration(self, start_date, end_date):
        """
        Calculate the duration of a leave request for this leave type
        
        Args:
            start_date (date): Start of leave period
            end_date (date): End of leave period
        
        Returns:
            int: Number of working days in the leave period
        """
        return calculate_leave_duration(start_date, end_date)