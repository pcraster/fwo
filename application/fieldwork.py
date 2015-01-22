import os
import requests
import glob
import shutil
import json
import random
import subprocess
import datetime

#
#todo: 		xx	update existing single map layer
#			xx	basemap update buttons when version is outdated. red->green reload button
#			xx	version number in the basemap window of the project
#			xx	delete uploaded files
#				docs/refactoring/use appropriate template and view names
#				harden map update script, return proper error codes - web app should reflect these!!
#			xx	security fixes, make sure you can't see each others maps
#			xx	duplicate wms keys
#			xx	last activity/wms url on overview page
#				make self check function which tests some required settings/functionality/paths/etc.
#				backup script
#
from flask import Flask, render_template, request, redirect, abort, flash, send_file, send_from_directory, url_for, make_response, Response

from flask.ext.mail import Mail
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.user import current_user, login_required, roles_required, UserManager, UserMixin, SQLAlchemyAdapter
from slugify import slugify

from PyQt4.QtCore import QFileInfo
from qgis.core import *

QgsApplication([], True)
QgsApplication.initQgis()
#make sure to install libqt4-dev python-qt4

app = Flask(__name__)
app.config.from_object("settings")

# Load local_settings.py if file exists
try: 
	app.config.from_object('local_settings')
except: 
	pass

if not os.access(app.config["DATADIR"], os.W_OK):
	print " * No write access to data directory %s"%(app.config["DATADIR"])
	sys.exit()


print " * Database is at %s"%(app.config["SQLALCHEMY_DATABASE_URI"])
print " * %s"%(app.config["SERVER_NAME"])

# Initialize Flask extensions
db = SQLAlchemy(app)
mail = Mail(app)

# Define User model. Make sure to add flask.ext.user UserMixin!!
class User(db.Model, UserMixin):
	id = db.Column(db.Integer, primary_key=True)
	active = db.Column(db.Boolean(), nullable=False, default=False)
	username = db.Column(db.String(50), nullable=False, unique=True)
	fullname = db.Column(db.String(50), nullable=True, unique=False, default='')
	password = db.Column(db.String(255), nullable=False, default='')
	email = db.Column(db.String(255), nullable=False, unique=True)
	confirmed_at = db.Column(db.DateTime())
	reset_password_token = db.Column(db.String(100), nullable=False, default='')
	roles = db.relationship('Role', secondary='user_roles', backref=db.backref('users', lazy='dynamic'))
	#err.. don't cascade??
	current_project = db.Column(db.Integer(), db.ForeignKey('campaign.id'),nullable=True)
	def __repr__(self):
		return "<User: %s CurrentProject: %s>"%(self.username,self.current_project)
	def __init__(self, **kwargs):
		self.username=kwargs["username"]
		self.fullname=kwargs["fullname"] if "fullname" in kwargs else ''
		self.email=kwargs["email"]
		self.active=True
		self.password=user_manager.hash_password(kwargs["password"])
		self.add_role("student")
	@property
	def is_supervisor(self):
		return self.has_role("supervisor")

	@property
	def is_admin(self):
		return self.has_role("administrator")

	@property
	def is_student(self):
		return self.has_role("student")
	@property
	def role_list(self):
		return [role.name for role in self.roles]

	def has_role(self,role_name):
		"""
		Checks if a user is assigned a particular role or not.

		Returns true if a user has the specified role, and false otherwise
		"""
		for role in self.roles:
			if role.name==role_name:
				return True
		return False
	def add_role(self,role_name):
		"""
		Adds a specific role to a user.

		"""
		role=Role.query.filter(Role.name==role_name).first()
		if role and not self.has_role(role_name):
			self.roles.append(role)
			db.session.commit()
			return True
		else:
			return False
	def rem_role(self,role_name):
		role=Role.query.filter(Role.name==role_name).first()
		if role and self.has_role(role_name):
			self.roles.remove(role)
			db.session.commit()
			return True
		else:
			return False

	def enroll_with_invite_key(self,invite_key):
		campaign=Campaign.query.filter_by(invite_key=invite_key).first()
		if campaign:
			campaign.enroll_user(self.id)
			return True
		else:
			return False
	@property
	def basemap(self):
		pass

	@property
	def working_on(self):
		"""
		Return the project the user is currently working on.
		"""
		pass
	@property
	def slug(self):
		return slugify("%i-%s"%(self.id,self.username))

	@property
	def current_projects(self):
		if current_user.is_admin:
			return Campaign.query.all()
		else:
			return Campaign.query.filter(Campaign.users.any(id=self.id)).all()


# Define Role model
class Role(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)
    def __repr__(self):
    	return name

# Define UserRoles model
class UserRoles(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	user_id = db.Column(db.Integer(), db.ForeignKey('user.id', ondelete='CASCADE'))
	role_id = db.Column(db.Integer(), db.ForeignKey('role.id', ondelete='CASCADE'))

class Campaign(db.Model):
	id =  db.Column(db.Integer(), primary_key=True)
	name = db.Column(db.String(50), nullable=False, unique=True)
	description = db.Column(db.String(255), nullable=False, unique=False)
	slug = db.Column(db.String(50), nullable=False, unique=True)
	invite_key = db.Column(db.String(50), nullable=True)
	users = db.relationship('User', secondary='campaign_users', backref=db.backref('campaigns',lazy='dynamic'))
	basemap_version = db.Column(db.DateTime())
	allow_feedback = db.Column(db.Boolean(), nullable=False, default=True)
	allow_collaborate = db.Column(db.Boolean(), nullable=False, default=True)

	def __init__(self,name,description):
		self.name=name
		self.description=description
		random.seed()
		self.invite_key=''.join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
		self.slug=slugify(name)
		basedir=self.basedir
		if not os.path.isdir(basedir):
			os.makedirs(basedir)
			os.makedirs(os.path.join(basedir,"userdata"))
			os.makedirs(os.path.join(basedir,"projectdata","map"))
			os.makedirs(os.path.join(basedir,"projectdata","attachments"))

	def __repr__(self):
		return "<Campaign: /campaigns/%s>"%(self.slug)
	@property
	def time_basemap(self):
		if self.basemap_version:
			return self.basemap_version
		else:
			return datetime.datetime(2000, 8, 4, 12, 30, 45)
	@property
	def basedir(self):
		return os.path.join(app.config["DATADIR"],"campaigns",self.slug)
	@property
	def projectdata(self):
		return os.path.join(app.config["DATADIR"],"campaigns",self.slug,"projectdata")
	@property
	def basemap(self):
		"""
		Returns the filename of the basemap for this project. Returns False if no basemap has been uploaded.
		"""
		projectfiles=glob.glob(os.path.join(self.basedir,"projectdata","map")+"/*.qgs")
		try: 
			return projectfiles[0]
		except: 
			return False
	@property
	def enrolled_users(self):
		"""
		Returns the number of users in this project.
		"""
		return len(self.users)
	def userdata(self,user_id):
		"""
		Returns the userdata directory for a particular user in this fieldwork project.
		"""
		user=User.query.filter(User.id==int(user_id)).first()
		userdir=os.path.join(self.basedir,"userdata",user.slug)
		if not os.path.isdir(userdir):
			os.makedirs(userdir)
			os.makedirs(os.path.join(userdir,"map"))
			os.makedirs(os.path.join(userdir,"attachments"))
			#shutil.copy("template.sqlite",os.path.join(userdir,"features.sqlite"))
		return userdir
	def basemap_for(self,user_id=None):
		projectfiles=sorted(glob.glob(os.path.join(self.userdata(user_id),"map")+"/*.qgs"), key=os.path.getmtime)
		try: 
			return projectfiles[-1]
		except: 
			return False
	def projectdata_for(self,user_id=None):
		"""
		Returns a CampaignUsers object in which the configuration and other data is stored for a user's enrollment in a project. For example when then basemap was last updated, when the user was last seen online.
		"""
		try:
			return CampaignUsers.query.filter(CampaignUsers.campaign_id==self.id,CampaignUsers.user_id==user_id).first()
		except Exception as e:
			print e
			return None

	def basemap_update(self,user_id=None):
		"""
		Update the basemap for users enrolled in this project. If no user_id supplied the basemap is updated for all users enrolled in this project, otherwise only for the user provided. This option usually occurs when the user is first enrolled in a project, or when a user updates his data.

		Actually updating the basemap is done by a standalone script "clone-qgis-fieldwork-project.py" which is located in the ~/scripts/ subdirectory of the fieldwork app. This script is called using subprocess and should return code 0 for success. Anyhting else means something went wrong. This action is done by a separate script to avoid having to use the QGIS API (which is a bit unstable sometimes) from within the web application. This way if the script crashes or whatever, it will just return status != 0 and we can report the error in the web app without breaking anything else.
		"""
		try:
			users=[User.query.filter(User.id==int(user_id)).first()]
		except:
			users=self.users
		if self.basemap:
			for user in users:
				target=self.userdata(user.id)
				script=os.path.join(app.config["APPDIR"],"scripts","clone-qgis-fieldwork-project.py")
				cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==self.id,CampaignUsers.user_id==user.id).first()
				try:
					cmd=["/usr/bin/python",script,"--clone",self.basemap,"--target",target]
					child=subprocess.Popen(cmd, stdout=subprocess.PIPE)
					streamdata=child.communicate()[0]
					returncode=child.returncode	
					if returncode==0:
						cu.time_basemapversion=db.func.now()
						db.session.commit()
						flash("Reloaded basemap data for user <code>%s</code>"%(user.username),"ok")
					else:
						flash("Failed to reload basemap data for user <code>%s</code>. The map update script returned status code <code>%d</code>."%(user.username,returncode),"error")
						flash("Script output: <code>%s</code>"%(streamdata),"error")
				except Exception as e:
					flash("Failed to reload basemap data for user <code>%s</code>. An exception occurred while trying to run the map update script. Hint: %s"%(user.username,e),"error")
			return True
		else:
			flash("Basemap could not be updated because no basemap has been uploaded in this project.","error")
			return False

	def enroll_user(self,user_id):
		"""
		Enrolls a user in this fieldwork campaign.

		- add the reference in the database
		- create the user directory in the project's userdata folder
		- clone the basemap into the userdata 
		"""
		try:
			user=User.query.filter(User.id==int(user_id)).first()
			enrollment=CampaignUsers.query.filter(CampaignUsers.campaign_id==self.id,CampaignUsers.user_id==user.id).count()
			if enrollment==0:
				#use not yet enrolled...
				userdir=self.userdata(user_id)
				self.users.append(user)
				db.session.commit()
				self.basemap_update(user_id)
				flash("User <code>%s</code> has been successfully enrolled in the fieldwork project %s"%(user.username,self.name),"ok")
				return True
			else:
				#user already enrolled.
				flash("User <code>%s</code> is already enrolled in this fieldwork project %s"%(user.username,self.name),"ok")
				return True
		except Exception as e:
			flash("Failed to enroll user <code>%s</code> in the fieldwork project %s. Hint: %s"%(user.username,self.name,e),"error")
			return False
	def features(self,user_id):
		"""
		Returns an overview of the feature data which has been uploaded by the user (via spreadsheets) and is saved in the "features.sqlite" file in the userdata directory.
		"""
		features=[]
		try:
			from pyspatialite import dbapi2 as spatialite
			conn = spatialite.connect(self.features_database(user_id))
			cur = conn.cursor()
			rs = cur.execute("SELECT name,title,features,description FROM fwo_metadata")
			for row in rs: 
				features.append(row)
			return features
		except Exception as e:
			flash("Could not load the table of custom features. Probably no features have been uploaded yet by this user.","info")
			return []
	def features_database(self,user_id):
		"""
		Returns the full path to the features.sqlite file, which contains the feature data that has been uploaded by the user. When no data has been uploaded yet this file does not exist.
		"""
		return os.path.join(self.userdata(user_id),"map","features.sqlite")

	def attachments(self,user_id):
		"""
		Returns a list of attachments that the specified user has uploaded to this project. Use sorted(glob.glob(...), key=os.path.getmtime) to sort by modification time instead.
		"""
		files=sorted(glob.glob(os.path.join(self.userdata(user_id),"attachments")+"/*.*"))
		for f in files:
			try:
				(head,tail)=os.path.split(f)
				extension=os.path.splitext(f)[1].lower()
				if extension.endswith((".png",".jpg",".jpeg")): filetype="image" 
				elif extension.endswith((".xls",".xlsx")): filetype="spreadsheet" 
				elif extension.endswith((".doc",".docx",".pdf",".txt")): filetype="document"
				else: filetype="other"
				yield {
					'name':tail,
					'type':filetype,
					'extension':extension,
					'size':os.path.getsize(f)
				}
			except Exception as e:
				pass

def generate_wms_key():
	random.seed()
	return ''.join(random.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(12))

class CampaignUsers(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	campaign_id = db.Column(db.Integer(), db.ForeignKey('campaign.id', ondelete='CASCADE'))
	user_id = db.Column(db.Integer(), db.ForeignKey('user.id', ondelete='CASCADE'))
	time_enrollment = db.Column(db.DateTime, nullable=False, default=db.func.now())
	time_basemapversion = db.Column(db.DateTime())
	time_lastactivity = db.Column(db.DateTime())
	wms_key = db.Column(db.String(50),nullable=True,default=generate_wms_key)
	campaign=db.relationship(Campaign,backref="memberships")
	user=db.relationship(User,backref="memberships")
	def update_lastactivity(self):
		self.time_lastactivity=db.func.now()
		db.session.commit()
	@property 
	def wms_url(self):
		if self.wms_key:
			return "http://%s/wms/%s"%(request.host,self.wms_key)
		else:
			return None
	@property
	def time_basemap(self):
		if self.time_basemapversion:
			return self.time_basemapversion
		else:
			return datetime.datetime(2000, 8, 4, 12, 30, 45)
	@property
	def text_lastactivity(self):
		if not self.time_lastactivity:
			return "No data uploaded yet"
		else:
			delta=datetime.datetime.utcnow()-self.time_lastactivity
			if delta.seconds < 60:
				return "Less than one minute ago"
			if delta.seconds < 3600:
				return "%d minutes ago"%(delta.seconds//60)
			if delta.seconds < 86400:
				return "%d hours ago"%(delta.seconds//(60*60))
			else:
				return self.time_lastactivity.strftime("%a %d %B at %H:%M")


db.create_all()

# Setup Flask-User
db_adapter = SQLAlchemyAdapter(db,  User)       # Select database adapter
user_manager = UserManager(db_adapter, app)     # Init Flask-User and bind to app



@app.route("/")
@login_required
def home():
	if not current_user.current_project:
		#always go to settings if user has not picked a project to work on yet.
		return redirect(url_for('settings_page'))
	else:
		#user has picked a project, now redirect to the project overview if user
		#is a supervisor or admin, and otherwise to the users workspace within
		#that project.
		project=Campaign.query.filter(Campaign.id==current_user.current_project).first()
		if (project) and (not current_user.is_admin) and (not current_user.is_supervisor):
			#user is not an admin and not a supervisor
			return redirect(url_for('project_page',slug=project.slug,user_id=current_user.id))
		elif (project) and ((current_user.is_admin) or (current_user.is_supervisor)):
			return redirect(url_for('project_userlist',slug=project.slug))
		else:
			return redirect(url_for('settings_page'))

@app.route("/admin",methods=["GET","POST"])
@login_required
@roles_required("administrator")
def admin():
	if request.method=="POST":
		if request.form.get("action","")=="project_create":
			try:
				campaign = Campaign(name=request.form.get("project_name"),description=request.form.get("project_description"))
				db.session.add(campaign)
				db.session.commit()
				subprocess.call(['chmod', '-R', '777', campaign.basedir])
				flash("Created a new project <code>%s</code>"%(campaign.name),"ok")
			except Exception as e:
				db.session.rollback()
				flash("Failed to create new project. Verify that the name and project slug do not exist yet.","error")
	if request.method=="GET":
		action=request.args.get("action","")
		if action=="add_role" or action=="rem_role":
			try:
				user=User.query.filter_by(id=request.args.get("user_id","")).first()
				role=request.args.get("role_name","")
				if action=="add_role":
					user.add_role(role)
					flash("Added role <code>%s</code> to user <code>%s</code>"%(role,user.username),"ok")
				if action=="rem_role":
					user.rem_role(role)
					flash("Removed role <code>%s</code> from user <code>%s</code>"%(role,user.username),"ok")
			except Exception as e:
				flash("An error occurred while modifying user's role. Hint:%s"%(e),"error")
			return redirect(url_for('admin'))
	return render_template("admin.html",users=User.query.all(),campaigns=Campaign.query.all(),roles=Role.query.all())

@app.route("/settings",methods=["GET","POST"])
@login_required
def settings_page():
	if request.method=="POST":
		if current_user.enroll_with_invite_key(request.form.get("invite_key","")):
			flash("You have been enrolled in a new fieldwork project!","ok")
		else:
			flash("Sorry, no fieldwork project could be found with that invite key.","error")
	if request.method=="GET" and request.args.get("workon","") != "":
		flash("Workon a different project!")
	current_projects=current_user.current_projects
	num_of_projects=len(current_projects)
	if num_of_projects==0:
		flash("Oops! It seems like you are currently not enrolled in any fieldwork campaigns. Contact your supervisor or enter an invitation key for your fieldwork on your <a href='/settings'>settings page</a>.","info")
	return render_template("settings.html",project_list=current_projects)

@app.route("/projects/",methods=["GET","POST"])
@login_required
def project_list():
	if request.method=="POST":
		if current_user.enroll_with_invite_key(request.form.get("invite_key","")):
			flash("You have been enrolled in a new fieldwork project!","ok")
		else:
			flash("Sorry, no fieldwork project could be found with that invite key.","error")
	current_projects=current_user.current_projects
	num_of_projects=len(current_projects)
	if num_of_projects==0:
		return redirect(url_for('settings_page'))
	else:
		return render_template("project-list.html",project_list=current_projects)

@app.route("/projects/<slug>/",methods=["GET","POST"])
@login_required
def project_userlist(slug=None):
	"""
	Shows the main project view for supervisors. It has a list of users and links to enroll other users which are not participating in the project yet. It is also possible to update the basemap for the project here by uploading a zip file (which will be unzipped) or individual files into the project's basemap directory.

	If this view is requested by a student user, the user is redirected directly to the student's project page.
	"""
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	#cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first()
	#Set the users working on 
	current_user.current_project=project.id
	db.session.commit()

	if current_user.is_admin or current_user.is_supervisor:
		#
		#If user is an admin or supervisor, show the project overview page
		#
		if request.method=="POST":
			f = request.files['uploadfile']
			if f and request.form.get("action","")=="upload":
				upload_file=os.path.join(project.projectdata,"map",f.filename)
				f.save(upload_file)
				if f.filename.endswith(".zip"):
					try:
						import zipfile
						with zipfile.ZipFile(upload_file) as zf:
							zip_filelist=zf.namelist()
							zip_details="Extracted %s files: <code>"%(len(zip_filelist))+"</code> <code>".join(zip_filelist)+"</code>"
							zf.extractall(os.path.join(project.projectdata,"map"))
							flash("Zip file detected! %s"%zip_details,"ok")
							project.basemap_version=db.func.now()
							db.session.commit()
					except Exception as e:
						flash("Zip file could not be extracted! Hint: %s"%(e),"error")
				flash("File <code>%s</code> was uploaded to the project basemap. Timestamp: <code>%s</code>"%(f.filename,project.basemap_version),"ok")
			elif request.form.get("action","")=="clearall":
				flash("Clearing all basemap data!","ok")
			elif request.form.get("action","")=="reload":
				project.basemap_update()
		if request.method=="GET":
			if request.args.get("action","")=="reload" and request.args.get("user_id","") != "":
				project.basemap_update(request.args.get("user_id",""))
			if request.args.get("action","")=="enroll" and request.args.get("user_id","") != "":
				project.enroll_user(request.args.get("user_id",""))

		users=User.query.filter(User.campaigns.contains(project)).all()
		enrollable_users=User.query.filter(~User.campaigns.contains(project)).all()
		return render_template("project-userlist.html",project=project,users=users,enrollable_users=enrollable_users)
	else:
		#
		#Else forward the user to the user's fieldwork homepage
		#
		return redirect(url_for('project_page',slug=project.slug,user_id=current_user.id))



@app.route("/projects/<slug>/<user_id>/")
@login_required
def project_page(slug=None,user_id=None):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	return render_template("project.html",project=project,user=user)

#@app.route("/projects/<slug>/<user_id>/wms")
@app.route("/wms/<wms_key>")
def wmsproxy(wms_key=None):
	"""
	This view acts as a HTTP proxy for the WMS server. There are a few reasons for going through the trouble of making a proxy:

	- Due to same origin policy the GetFeatureInfo requests need to originate on the same host. By having having a proxy this is guaranteed and it is possible to switch WMS servers on the fly if the need arises.
	- Sometimes QGIS server (if CRS restrictions have not been set manually in the project preferences) will return in XML a list of hundreds of allowed CRSes for each layer. This seriously bloats the GetProjectInfo request (it can become a 4MB+ file...). In this proxy we can manually limit the allowed CRSes to ensure the document does not become huge.
	- QGIS server does not support json responses! Since we are handling a lot of these WMS requests using JavaScript (also the GetFeatureInfo requests) it would be a lot easier, faster, and result in cleaner code, if the WMS server just returned JSON documents. Using this proxy we can add json support if the request argument FORMAT is set to "application/json", and do the conversion serverside with xmltodict. A JSONP callback argument is also supported.
	- We can camouflage the MAP parameter. This usually takes a full pathname to the map file. However, we dont want to reveal this to the world and let everybody mess about with it. Therefore we can override the MAP parameter in the proxy from the URL, that way the URL for a fieldwork WMS server will be /projects/fieldwork-demo/3/wms?<params> which is a lot neater than /cgi-bin/qgisserv.fcgi?MAP=/var/fieldwork-data/.....etc. There will be no MAP attribute visible to the outside in that case since it is added only on the proxied requests.
	- There are some opportunities for caching/compressing WMS requests at a later time if we use this method
	- We can limit access to the fieldwork data to only logged in users, or allow a per-project setting of who should be able to access the wms data.
	"""
	cu=CampaignUsers.query.filter(CampaignUsers.wms_key==wms_key).first_or_404()

	#project=Campaign.query.filter_by(slug=slug).first_or_404()
	project=Campaign.query.get(cu.campaign_id)
	user=User.query.get(cu.user_id)
	#user=User.query.filter_by(id=user_id).first_or_404()

	import xmltodict
	requestparams=dict(request.args) #we need something which is mutable...
	#requestparams.pop("MAP") #don't send the map param
	mapfile=project.basemap_for(user.id)
	requestparams.update({'MAP':mapfile})

	jsonp=request.args.get("JSONP","")
	if(jsonp):
		requestparams.pop("JSONP") #never send a JSONP parameter to the qgis server
	if(request.args.get("FORMAT","")=="application/json"):
		requestparams.update({'FORMAT':"text/xml"}) #always request xml from qgis server
	if(request.args.get("INFO_FORMAT","")=="application/json"):
		requestparams.update({'INFO_FORMAT':"text/xml"}) #always request xml from qgis server
	r=requests.get(app.config["WMS_SERVER_URL"],params=requestparams)
	print "Proxying request to: "+r.url
	if r.status_code==200:
		if r.headers['content-type']=="text/xml" and ( request.args.get("FORMAT","")=="application/json" or request.args.get("INFO_FORMAT","")=="application/json"):
			#if json was requested and we received xml from the server, then convert it...
			jsonresponse=json.dumps(xmltodict.parse(r.text.replace(app.config["WMS_SERVER_URL"],request.base_url)), sort_keys=False,indent=4, separators=(',', ': '))
			jsonresponse=jsonp+"("+jsonresponse+")" if jsonp!="" else jsonresponse
			return Response(jsonresponse,mimetype="application/json")
		elif r.headers['content-type']=="text/xml":
			#if xml was requested and xml was received, then just update the server urls in the response to the url of the wms proxy
			return Response(r.text.replace(app.config["WMS_SERVER_URL"],request.base_url),mimetype=r.headers['content-type'])
		else:
			#all other cases don't modify anything and just return whatever qgis server responded with
			return Response(r.content,mimetype=r.headers['content-type'])
	else:
		return Response("<pre>WMS server at %s returned status %i.</pre>"%(app.config["WMS_SERVER_URL"],r.status_code),mimetype="text/html")


@app.route("/projects/<slug>/<user_id>/enroll")
@login_required
@roles_required("administrator")
def project_enroll(slug=None,user_id=None):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	project.enroll_user(user.id)
	return redirect(url_for('project_userlist',slug=slug))

@app.route("/projects/<slug>/<user_id>/file",methods=["GET","POST","HEAD"])
@login_required
def project_file(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first()
	userdata=project.userdata(user.id)
	if request.method=="HEAD" or request.method=="GET":
		filename=request.args.get("filename","")
		if filename != "":
			as_attachment = True if not filename.lower().endswith((".png",".jpg",".jpeg")) else False
			return send_from_directory(os.path.join(userdata,"attachments"), filename, as_attachment=as_attachment)
	if request.method=="POST":
		try:
			from utils import excel_parser
			f = request.files['uploadfile']
			if f:
				upload_file=os.path.join(userdata,"attachments",f.filename)
				f.save(upload_file)
				if f.filename.endswith((".xls",".xlsx")):
					spatialite_file=project.features_database(user_id)
					excel_parser(upload_file,spatialite_file)
					project.basemap_update(user_id)
					cu.update_lastactivity()

				flash("Upload and processing of file <code>%s</code> completed."%(f.filename),"ok")
		except Exception as e:
			flash("An error occurred during the upload. Hint: %s"%(e),"error")
	return redirect(url_for('upload',slug=slug,user_id=user_id))

@app.route("/projects/<slug>/<user_id>/data",methods=["GET"])
@login_required
def upload(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()

	if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
		return render_template("denied.html")

	attachments=project.attachments(user_id)
	features=project.features(user_id)
	return render_template("upload.html",project=project,user=user,attachments=attachments,features=features)

@app.route("/projects/<slug>/<user_id>/feedback")
@login_required
def project_feedback(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
		return render_template("denied.html")

	return render_template("feedback.html",project=project,user=user)

@app.route("/projects/<slug>/<user_id>/collaborate")
@login_required
def project_collaborate(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
		return render_template("denied.html")

	cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first()
	return render_template("collaborate.html",project=project,user=user,cu=cu)


@app.route("/projects/<slug>/<user_id>/maps")
@login_required
def project_maps(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first()

	if not project.basemap:
		flash("No basemap has been uploaded by project administrator yet.","error")
	#else:
	#	flash("Basemap is <code>%s</code>"%(project.basemap),"info")
	usermap=project.basemap_for(user_id)
	#flash("User map is <code>%s</code>"%(usermap),"info")
	#project_toc=project.table_of_contensts
	#return render_template("maps.html",project=project,user=user,toc=project_toc)
	return render_template("maps.html",project=project,user=user,wms_key=cu.wms_key)

@app.route("/install")
def install():
	"""
		Installs the fieldwork online app.
	"""
	if os.path.isfile(os.path.join(app.config["DATADIR"],"install.txt")):
		flash("The application is already installed! Remove the <code>install.txt</code> file before re-installing the application.","error")
	else:
		try:
			messages=[]
			if User.query.count()==0:
				db.session.add_all([
					Role(name="administrator"),
					Role(name="supervisor"),
					Role(name="student")
				])
				db.session.commit()
				flash("Created <code>administrator</code>, <code>supervisor</code> and <code>student</code> roles.","ok")

				admin = User(username='admin', fullname='Site Admin', email='kokoalberti@yahoo.com', active=True, password='admin')
				admin.roles.append(Role.query.filter(Role.name=='administrator').first())
				admin.roles.append(Role.query.filter(Role.name=='supervisor').first())

				supervisor = User(username='supervisor', fullname='Site Supervisor', email='k.alberti@uu.nl', active=True, password='supervisor')
				supervisor.roles.append(Role.query.filter(Role.name=='supervisor').first())

				student = User(username='student', fullname='Sam Student', email='k.alberti@students.uu.nl', active=True, password='student')
				student.roles.append(Role.query.filter(Role.name=='student').first())

				db.session.add_all([admin,supervisor,student])
				db.session.commit()
				flash("Created a user <code>admin</code> with password <code>admin</code>","ok")
				flash("Created a user <code>supervisor</code> with password <code>supervisor</code>","ok")
				flash("Created a user <code>student</code> with password <code>student</code>","ok")

				campaign = Campaign(name="Demo Project",description="A fieldwork campaign for demonstration purposes. This project showcases basic functionality and lets you try out the interface.")
				campaign.users.append(admin)
				db.session.add(campaign)
				db.session.commit()
				flash("Created a fieldwork project for demo purposes. It is called <code>Fieldwork Online Demo Project</code>. Users can enroll themselves with the invite key <code>%s</code>"%(campaign.invite_key),"ok")
				flash("You can now log in via the <a href='/'>Fieldwork Online Homepage</a>.","info")
			else:
				flash("There are already users defined in the database. Please delete the database file <code>fieldwork.sqlite</code>, restart the application, and reload this page.","error")
		except Exception as e:
			flash("An error occurred while trying to install the base application. Hint:%s"%(e),"error")
	return render_template("install.html")

def selfcheck():
	"""
	Checks environment settings and read/writability of folders and programs to make sure everything is in working order. Returns True if all is well and False otherwise.
	"""
	pass

if __name__ == "__main__":
    app.run(debug=True)



