from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.models import User

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user or user.role != 'admin':
            return jsonify({'message': 'Admin acess required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def approver_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user or user.role != 'approver':
            return jsonify({'message': 'Approver access required'}), 403
        return f(*args, **kwargs)
    return decorated_function