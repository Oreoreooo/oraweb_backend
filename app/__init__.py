from flask import Flask, jsonify, request
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
    
    # Configure CORS - Parse origins from environment variable
    cors_origins = app.config['CORS_ORIGINS']
    if isinstance(cors_origins, str):
        # If it's a string from environment variable, split it
        cors_origins = [origin.strip() for origin in cors_origins.split(',')]
    
    # Debug: Print CORS origins
    print(f"🔧 CORS Origins configured: {cors_origins}")
    
    CORS(app, resources={
        r"/*": {
            "origins": cors_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Content-Type", 
                "Authorization", 
                "ngrok-skip-browser-warning",
                "X-Requested-With",
                "Accept",
                "Origin"
            ],
            "supports_credentials": True,
            "expose_headers": ["Content-Type", "Authorization"],
            "send_wildcard": False,  # 重要：禁用通配符，确保credentials工作
            "vary_header": True      # 重要：添加Vary头，帮助浏览器正确处理CORS
        }
    })
    
    # Add explicit OPTIONS handler for preflight requests
    @app.before_request
    def handle_preflight():
        if request.method == "OPTIONS":
            response = jsonify({'status': 'OK'})
            origin = request.headers.get('Origin')
            
            # 只对配置的origins返回CORS头
            if origin in cors_origins:
                response.headers.add("Access-Control-Allow-Origin", origin)
                response.headers.add('Access-Control-Allow-Headers', "Content-Type,Authorization,ngrok-skip-browser-warning,X-Requested-With,Accept,Origin")
                response.headers.add('Access-Control-Allow-Methods', "GET,PUT,POST,DELETE,OPTIONS")
                response.headers.add('Access-Control-Allow-Credentials', 'true')  # 明确设置credentials
                response.headers.add('Vary', 'Origin')  # 帮助浏览器缓存处理
            
            return response
    
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
    
    # Add a root route for testing
    @app.route('/')
    def index():
        return jsonify({
            'message': 'ORA Backend API is running!',
            'status': 'online',
            'version': '1.0.0',
            'endpoints': {
                'auth': '/api/auth',
                'api': '/api',
                'health': '/health'
            }
        })
    
    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})
    
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