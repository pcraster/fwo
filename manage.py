#!/usr/bin/env python
import os
import datetime
import subprocess

from flask.ext.script import Manager, Shell, Server
#from application import app
from application.models import *

manager = Manager(app)
manager.add_command("runserver",Server())
manager.add_command("shell",Shell())

def random_password():
	return ''.join(random.choice("abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))

@manager.command
def test():
	"""
	Run tests, of which there are none at the moment...
	"""
	print " * Run tests here... "
	print app.config

@manager.command
def createdb():
	"""
	Create the database.
	"""
	db.create_all()
	initdb()

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
	Initialize the database with default data.

	* Add the administrator, supervisor, and student roles
	* Create an admin, supervisor, and student user
	* The random passwords are stored in install.txt in the data directory
	"""
	pw_admin=random_password()
	pw_supervisor=random_password()
	pw_student=random_password()

	db.session.add_all([
		Role(name="administrator"),
		Role(name="supervisor"),
		Role(name="student")
	])
	db.session.commit()

	flash("Created <code>administrator</code>, <code>supervisor</code> and <code>student</code> roles.","ok")

	admin = User(username='admin', fullname='Site Admin', email='kokoalberti@yahoo.com', active=True, password=user_manager.hash_password(pw_admin))
	admin.roles.append(Role.query.filter(Role.name=='administrator').first())
	admin.roles.append(Role.query.filter(Role.name=='supervisor').first())

	supervisor = User(username='supervisor', fullname='Site Supervisor', email='k.alberti@uu.nl', active=True, password=user_manager.hash_password(pw_supervisor))
	supervisor.roles.append(Role.query.filter(Role.name=='supervisor').first())

	student = User(username='student', fullname='Sam Student', email='k.alberti@students.uu.nl', active=True, password=user_manager.hash_password(pw_student))
	student.roles.append(Role.query.filter(Role.name=='student').first())

	db.session.add_all([admin,supervisor,student])
	db.session.commit()

	campaign = Campaign(name="Demo Project",description="A fieldwork campaign for demonstration purposes. This project showcases basic functionality and lets you try out the interface.")
	campaign.users.append(admin)
	db.session.add(campaign)
	db.session.commit()

	print " * Created default users, roles, and demo project."
	print " * User credentials (you way want to write these down, it is the only time they're visible):"
	print "    - Administrator: admin/%s"%(pw_admin)
	print "    - Supervisor: supervisor/%s"%(pw_student)
	print "    - Student: student/%s"%(pw_student)

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

@manager.command
@manager.option('-u', '--username', help='Username')
def reset_password(username):
	"""
	Hard reset of user password
	"""
	user=User.query.filter(User.username==username).one()
	pw_user=random_password()
	user.password=user_manager.hash_password(pw_user)
	db.session.commit()
	print "New password for %s: %s"%(username,pw_user)

if __name__=="__main__":
	manager.run()