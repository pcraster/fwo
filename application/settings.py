# Settings overridden by local_settings
DEBUG=True
SECRET_KEY=''
USERNAME=''
PASSWORD=''
SECRET_KEY = ''
CSRF_ENABLED = True
SQLALCHEMY_DATABASE_URI = '' 
#SERVER_NAME=''

# Development paths...
APPDIR="/var/www/fwo"
DATADIR="/var/wwwdata/fwo"

# Configure Flask-Mail -- Required for Confirm email and Forgot password features
MAIL_SERVER   = 'smtp.gmail.com'
MAIL_PORT     = 465
MAIL_USE_SSL  = True                            # Some servers use MAIL_USE_TLS=True instead
MAIL_USERNAME = 'badjas42@gmail.com'
MAIL_PASSWORD = ''
MAIL_DEFAULT_SENDER = '"Fieldwork Online" <noreply@fwo.com>'


# Configure Flask-User
USER_PRODUCT_NAME           = "Fieldwork Online"     # Used by email templates
USER_ENABLE_USERNAME        = True              # Register and Login with username
USER_ENABLE_EMAIL           = True              # Register and Login with email
USER_LOGIN_TEMPLATE         = 'flask_user/login_or_register.html'
USER_REGISTER_TEMPLATE      = 'flask_user/login_or_register.html'
USER_AFTER_LOGIN_ENDPOINT   = 'home'
USER_AFTER_CONFIRM_ENDPOINT = 'home'

USER_ENABLE_CONFIRM_EMAIL   = False 
USER_ENABLE_CHANGE_USERNAME = False
USER_SEND_PASSWORD_CHANGED_EMAIL = False
USER_SEND_REGISTERED_EMAIL = False
USER_SEND_USERNAME_CHANGED_EMAIL = False


# URLs                        # Default
USER_CHANGE_PASSWORD_URL      = '/user/change-password'
USER_CHANGE_USERNAME_URL      = '/user/change-username'
USER_CONFIRM_EMAIL_URL        = '/user/confirm-email/<token>'
USER_EMAIL_ACTION_URL         = '/user/email/<id>/<action>'     # v0.5.1 and up
USER_FORGOT_PASSWORD_URL      = '/user/forgot-password'
USER_LOGIN_URL                = '/user/login'
USER_LOGOUT_URL               = '/user/logout'
USER_MANAGE_EMAILS_URL        = '/user/manage-emails'
USER_REGISTER_URL             = '/user/register'
USER_RESEND_CONFIRM_EMAIL_URL = '/user/resend-confirm-email'    # v0.5.0 and up
USER_RESET_PASSWORD_URL       = '/user/reset-password/<token>'

