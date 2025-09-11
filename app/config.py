import os
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables
load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change-in-production'
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key-please-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    
    # 配置 Flask-Mail (163邮箱)
    MAIL_SERVER = 'smtp.163.com'
    MAIL_USE_SSL = True
    MAIL_PORT = 465
    MAIL_USERNAME = "xbao002@163.com"
    MAIL_PASSWORD = "XNTsi9X7FkLrMCJR"   # 有效期180天，start from 2025-6-20
    MAIL_DEFAULT_SENDER = "xbao002@163.com"
    
    # 不使用TLS，改用SSL
    MAIL_USE_TLS = False
    
    # MYSQL 数据库配置
    HOSTNAME = "localhost" 
    PORT = "3306"   
    USERNAME = "root"
    PASSWORD = "0119"
    DATABASE = "message"
    DB_URI = f"mysql+pymysql://{USERNAME}:{PASSWORD}@{HOSTNAME}:{PORT}/{DATABASE}?charset=utf8mb4"
    SQLALCHEMY_DATABASE_URI = DB_URI
    
    # Redis 配置
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = 6379
    REDIS_DB = 0           # 第 0 号数据库
    REDIS_PASSWORD = None  # 如果有密码则填写，否则为 None
    
    # ASR settings
    ASR_MODEL_PATH = os.environ.get('ASR_MODEL_PATH') or 'iic/SenseVoiceSmall'
    USE_CUDA = os.environ.get('USE_CUDA', 'False').lower() == 'true'
    
    # API Keys
    CHAT_API_KEY = os.getenv('CHAT_API_KEY')
    TEXT_REGENERATION_API_KEY = os.getenv('TEXT_REGENERATION_API_KEY')
    GPT_API_KEY = os.getenv('GPT_API_KEY')

    # Server settings
    HOST = os.environ.get('HOST') or 'localhost'
    PORT = int(os.environ.get('PORT') or 3002)
    DEBUG = True
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS') or [
        'http://localhost:3000',
        'http://localhost:3001', 
        'https://orawebfrontend-production.up.railway.app'  # 替换为你的Railway前端域名
    ]

    @classmethod
    def validate_config(cls):
        """Validate that all required configuration is present"""
        if not cls.CHAT_API_KEY:
            raise ValueError("CHAT_API_KEY is required")
        
        if not cls.TEXT_REGENERATION_API_KEY:
            raise ValueError("TEXT_REGENERATION_API_KEY is required")
        
        # Only check ASR model path if not in debug mode
        if not cls.DEBUG and not os.path.exists(cls.ASR_MODEL_PATH):
            raise ValueError(f"ASR model not found at {cls.ASR_MODEL_PATH}") 