from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required, 
    get_jwt_identity
)
from flask_mail import Message
from app.extension import mail, redis_client, db
from app.models import UserModel
from forms import RegisterForm, LoginForm
import random
from datetime import datetime, timedelta

# Create auth blueprint
auth_bp = Blueprint('auth', __name__)

# In-memory storage for verification codes (in production, use Redis)
verification_codes = {}

@auth_bp.route("/captcha/email")
def captcha_email():
    email = request.args.get("email")
    
    if not email:
        return jsonify({'code': 400, 'message': 'Email is required'}), 400
    
    # 生成6位数字验证码
    captcha = str(random.randint(100000, 999999))
    
    try:
        # 缓存验证码到 Redis，设置有效期5分钟
        redis_client.setex(f"captcha:{email}", 300, captcha)
        
        # 发送邮件
        message = Message(
            subject="Ora - Email Verification Code",
            recipients=[email],
            body=f"""Dear User,

Your verification code for Ora registration is: {captcha}

This code will expire in 5 minutes.

If you didn't request this verification code, please ignore this email.

Best regards,
Ora Team"""
        )
        mail.send(message)
        
        return jsonify({
            "code": 200, 
            "message": "Verification code sent successfully to your email"
        })
        
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        # 开发模式：在控制台显示验证码
        print(f"Verification code for {email}: {captcha}")
        return jsonify({
            "code": 200, 
            "message": "Email service error. Verification code logged to console.",
            "development_code": captcha  # 移除这行在生产环境
        })

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    User registration with email verification
    """
    data = request.get_json()
    
    # Validate required fields  
    if not all(k in data for k in ['username', 'email', 'password', 'captcha']):
        return jsonify({'message': 'Missing required fields'}), 400
    
    # Verify captcha code from Redis
    email = data['email']
    provided_code = data['captcha']
    
    # Get captcha from Redis
    stored_captcha = redis_client.get(f"captcha:{email}")
    if not stored_captcha:
        return jsonify({'message': 'No verification code sent for this email'}), 400
    
    stored_captcha = stored_captcha.decode('utf-8')  # Redis returns bytes
    if provided_code != stored_captcha:
        return jsonify({'message': 'Invalid verification code'}), 400
    
    # Remove used verification code
    redis_client.delete(f"captcha:{email}")
    
    # Check if user already exists
    if UserModel.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'User already exists'}), 400
    
    # Create new user
    user = UserModel(
        username=data['username'],
        email=data['email'],
        password=generate_password_hash(data['password'])
    )
    
    try:
        db.session.add(user)
        db.session.commit()
        
        # Create tokens
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'success': True,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Server error'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    User login
    """
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ['email', 'password']):
        return jsonify({'message': 'Missing required fields'}), 400
    
    # Find user
    user = UserModel.query.filter_by(email=data['email']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    # Create tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    return jsonify({
        'success': True,
        'token': access_token,
        'refresh_token': refresh_token,
        'user': user.to_dict()
    })

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token
    """
    current_user_id = get_jwt_identity()
    user = UserModel.query.get(current_user_id)
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    access_token = create_access_token(identity=current_user_id)
    return jsonify({
        'access_token': access_token,
        'user': user.to_dict()
    })

@auth_bp.route('/user', methods=['GET'])
@jwt_required()
def get_user():
    """
    Get current user info
    """
    current_user_id = get_jwt_identity()
    user = UserModel.query.get(current_user_id)
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    return jsonify(user.to_dict())

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    User logout
    """
    # In a real application, you might want to blacklist the token
    # For now, we'll just return a success message
    return jsonify({'message': 'Successfully logged out'})

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """
    Change user password
    """
    current_user_id = get_jwt_identity()
    user = UserModel.query.get(current_user_id)
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ['current_password', 'new_password']):
        return jsonify({'message': 'Missing required fields'}), 400
    
    # Check current password
    if not user.check_password(data['current_password']):
        return jsonify({'message': 'Current password is incorrect'}), 400
    
    # Update password
    user.set_password(data['new_password'])
    
    try:
        db.session.commit()
        return jsonify({'message': 'Password changed successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Server error'}), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Reset password with email verification
    """
    data = request.get_json()
    
    # Validate required fields
    if not all(k in data for k in ['email', 'captcha', 'new_password']):
        return jsonify({'message': 'Missing required fields'}), 400
    
    email = data['email']
    provided_code = data['captcha']
    
    # Verify captcha code
    if email not in verification_codes:
        return jsonify({'message': 'No verification code sent for this email'}), 400
    
    stored_data = verification_codes[email]
    if datetime.now() > stored_data['expires_at']:
        del verification_codes[email]
        return jsonify({'message': 'Verification code has expired'}), 400
    
    if provided_code != stored_data['code']:
        return jsonify({'message': 'Invalid verification code'}), 400
    
    # Remove used verification code
    del verification_codes[email]
    
    # Find user
    user = UserModel.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    # Update password
    user.set_password(data['new_password'])
    
    try:
        db.session.commit()
        return jsonify({'message': 'Password reset successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Server error'}), 500
