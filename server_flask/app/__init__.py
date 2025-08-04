from flask import Flask, jsonify
from flask_cors import CORS
from app.extension import db, jwt, mail
from .routes import bp
from .auth import auth_bp
from app.models import UserModel, Conversation, ChatMessage
from .config import Config
from datetime import datetime

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)
    
    # Configure CORS
    CORS(app, resources={
        r"/*": {
            "origins": ["http://localhost:3000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'status': 401,
            'sub_status': 42,
            'msg': 'The token has expired'
        }), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'status': 401,
            'sub_status': 42,
            'msg': 'Invalid token'
        }), 401

    @jwt.unauthorized_loader
    def unauthorized_callback(error):
        return jsonify({
            'status': 401,
            'sub_status': 42,
            'msg': 'Missing authorization header'
        }), 401

    # JWT user loader
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        return UserModel.query.filter_by(id=identity).one_or_none()
    
    # Register blueprints
    app.register_blueprint(bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    
    # Initialize database and create test user
    with app.app_context():
        try:
            # Create database tables
            db.create_all()
            
            # Check if test user exists
            test_user = UserModel.query.filter_by(email='test@example.com').first()
            if not test_user:
                # Create test user
                test_user = UserModel(
                    name='Test User',
                    email='test@example.com'
                )
                test_user.set_password('password123')
                db.session.add(test_user)
                db.session.commit()
                print("Test user created successfully!")
            else:
                print("Test user already exists!")
        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            raise
    
    return app 