import wtforms
from wtforms import validators
from models import UserModel
from extension import redis_client


class RegisterForm(wtforms.Form):
    email = wtforms.StringField("Email", validators=[validators.DataRequired(), validators.Email(message="Invalid email address")])
    captcha = wtforms.StringField("Captcha", validators=[validators.DataRequired(), validators.Length(min=4, max=4, message="Captcha must be 4 characters")])
    username = wtforms.StringField("Username", validators=[validators.DataRequired(), validators.Length(min=1, max=50, message="Username must be between 3 and 50 characters")])
    password = wtforms.PasswordField("Password", validators=[validators.DataRequired(), validators.Length(min=6, max=20, message="Password must be between 6 and 20 characters")])
    password_confirm = wtforms.PasswordField("Confirm Password", validators=[validators.DataRequired(), validators.EqualTo("password", message="Passwords must match")])

    # 自定义验证
    # 1. 验证邮箱是否已注册
    def validate_email(self, email):
        email = email.data.strip()
        user = UserModel.query.filter_by(email=email).first()
        if user:
            raise validators.ValidationError("Email is already registered.")
    
    # 2. 验证码是否正确
    def validate_captcha(self, captcha):
        email = self.email.data.strip()
        cached_captcha = redis_client.get(f"captcha:{email}")
        if not cached_captcha or cached_captcha != captcha.data.strip():
            raise validators.ValidationError("Invalid or expired captcha.")
        
        
class LoginForm(wtforms.Form):
    email = wtforms.StringField("Email", validators=[validators.DataRequired(), validators.Email(message="Invalid email address")])
    password = wtforms.PasswordField("Password", validators=[validators.DataRequired(), validators.Length(min=6, max=20, message="Password must be between 6 and 20 characters")])