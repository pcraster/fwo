#!/usr/bin/env python
from flask.ext.script import Manager, Shell, Server
from application import app
from application.models import db

manager = Manager(app)

manager.add_command("runserver",Server())
manager.add_command("shell",Shell())

@manager.command
def createdb():
	"""
	Create the database.
	"""
	db.create_all()

@manager.command
def initdb():
	"""
	Initialize the database with some default data such as an admin
	user and a demo fieldwork campaign.
	"""
	pass

@manager.command
def dropdb():
	"""
	Drop the database. Use with care!
	"""
	db.drop_all()

@manager.command
def purgedb():
	"""
	Drop and create the database. Use with care!
	"""
	dropdb()
	initdb()
	createdb()

@manager.command
def createblueprint():
	"""
	Add a new blueprint to this project.
	"""
	pass


if __name__=="__main__":
	manager.run()