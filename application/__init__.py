#from flask import Flask, render_template, request, redirect, abort, flash, send_file, send_from_directory, url_for, make_response, Response


from flask import Flask
#from flask.ext.mail import Mail
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.user import UserManager, UserMixin, SQLAlchemyAdapter
#from flask.ext.user import current_user, login_required, roles_required, UserManager, UserMixin, SQLAlchemyAdapter
# from slugify import slugify


app = Flask(__name__)

app.config.from_object("application.settings")

# Load local_settings.py if file exists
try: app.config.from_object('application.local_settings')
except: pass

#app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db=SQLAlchemy(app)


from application import views, models


#db.create_all()
# Setup Flask-User


#from views import *


if __name__ == "__main__":
	app.run(debug=True)
