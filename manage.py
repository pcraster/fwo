#!/usr/bin/env python
import os
import datetime
import subprocess

from flask.ext.script import Manager, Shell, Server
from application import app
from application.models import db

manager = Manager(app)

manager.add_command("runserver",Server())
manager.add_command("shell",Shell())

@manager.command:
def test():
	"""
	Run tests, of which there are none at the moment...
	"""
	print " * Run tests here... "

@manager.command
def createdb():
	"""
	Create the database.
	"""
	db.create_all()

@manager.command
def clearuserdata():
	"""
	Will clear all userdata!!! Use with care!!!
	"""
	pass

@manager.command
def backup():
	"""
	Creates a backup of the entire site and database.
	"""
	_datadir=app.config["DATADIR"]
	backupfile=os.path.join(_datadir,"backup","fwo_backup_"+datetime.datetime.now().strftime("%Y%m%d_%H%M%S")+".tar.gz")
	c=[
		'/bin/tar',
		'zcf',
		backupfile,
		'-C',app.config["DATADIR"],
		'campaigns',
		'fieldwork.sqlite'
	]
	rc=subprocess.call(c)
	if(rc==0):
		print " * Backup ok! Saved to %s"%(backupfile)
	else:
		print " * Something went wrong! Tar command returned code %d"%(rc)

@manager.command
def initdb():
	"""
	Initialize the database with some default data such as an admin
	user and a demo fieldwork campaign.

	For now use a web view to do this at <host>/install
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