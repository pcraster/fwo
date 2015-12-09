from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

#Create Flask app
app = Flask(__name__)

#Load the configuration
app.config.from_object("application.settings")

#Load private config from local_settings.py
try: app.config.from_object('application.local_settings')
except: pass

#Load SQLAlachemy extension
db = SQLAlchemy(app)

#Import views and models
from application import views, models

if __name__ == "__main__":
	app.run(debug=True)
