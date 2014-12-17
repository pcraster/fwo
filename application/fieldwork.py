import os
import requests
import glob
import shutil
import json
import random

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
	@property
	def is_supervisor(self):
		return self.has_role("supervisor")

	@property
	def is_admin(self):
		return self.has_role("administrator")

	@property
	def is_student(self):
		return self.has_role("student")

	def has_role(self,role_name):
		for role in self.roles:
			if role.name==role_name:
				return True
		return False

	def enroll_with_invite_key(self,invite_key):
		campaign=Campaign.query.filter_by(invite_key=invite_key).first()
		if campaign:
			campaign.enroll_user(self.id)
			return True
		else:
			return False

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
	def __init__(self,name,description):
		self.name=name
		self.description=description
		self.invite_key=''.join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(6))
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
		projectfiles=glob.glob(os.path.join(self.basedir,"userdata","3-student","map")+"/cloned_project.qgs")
		try: return projectfiles[0]
		except: return False
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
			os.makedirs(os.path.join(userdir,"data"))
			os.makedirs(os.path.join(userdir,"map"))
			os.makedirs(os.path.join(userdir,"temp"))
			os.makedirs(os.path.join(userdir,"attachments"))
			shutil.copy("template.sqlite",os.path.join(userdir,"features.sqlite"))
		return userdir
	def enroll_user(self,user_id):
		"""
		Enrolls a user in this fieldwork campaign.

		enroll user <user_id> in this project.

		- add the reference in the database
		- create the user directory in the project's userdata folder
		- clone the basemap into the userdata 
		"""
		try:
			user=User.query.filter(User.id==int(user_id)).first()
			userdir=self.userdata(user_id)
			self.users.append(user)
			db.session.commit()
			return True
		except Exception as e:
			return False
	def features(self,user_id):
		"""
		Returns an overview of the feature data which has been uploaded by the user (via spreadsheets) and is saved in the "features.sqlite" file in the userdata directory.
		"""
		try:
			from pyspatialite import dbapi2 as spatialite
			conn = spatialite.connect(os.path.join(self.userdata(user_id),"features.sqlite"))
			cur = conn.cursor()
			rs = cur.execute("SELECT name,title,features,description FROM fwo_metadata")
			for row in rs: yield row
		except Exception as e:
			flash("Something went wrong trying try create the features table. Probably no features have been uploaded yet in a spreadsheet.","error")

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

	# @property
	# def table_of_contents(self):
	# 	"""
	# 	Returns a table of contents and map preferences for a project. The table of contents is read from the QGIS project of the user and stored in the "toc" node of the returned dict. Other nodes store the preferences which can be modified on a per user (viewer) basis, such as the layer visibilities, active layer, zoom level, location, and other map settings. This ensures that when a user is toggling layers on and off and panning in the map, that when they return to the map view the same view is presented as last time.
	# 	"""
	# 	return False
	# 	# _QgsLayerTypes=['vector','raster','plugin'] 
	# 	# proj=QgsProject.instance()
	# 	# proj.read(QFileInfo(self.basemap))
	# 	# def node_to_dict(node):
	# 	# 	nodes=[]
	# 	# 	for child in node.children():
	# 	# 		if isinstance(child, QgsLayerTreeGroup):
	# 	# 			nodes.append({
	# 	# 				'node':'group',
	# 	# 				'visible':False if child.isVisible()==0 else True,
	# 	# 				'collapse':False,
	# 	# 				'name':str(child.name()),
	# 	# 				'children':node_to_dict(child)
	# 	# 			})
	# 	# 		elif isinstance(child, QgsLayerTreeLayer):
	# 	# 			lyr=child.layer()
	# 	# 			nodes.append({
	# 	# 				'node':'layer',
	# 	# 				'visible':False if child.isVisible()==0 else True,
	# 	# 				'collapse':False,
	# 	# 				'name':str(child.layerName()),
	# 	# 				'type':_QgsLayerTypes[int(lyr.type())],
	# 	# 				'children':[]
	# 	# 			})
	# 	# 	return nodes
	# 	# return node_to_dict(proj.layerTreeRoot())

	# def add_file(self,file_path):
	# 	"""
	# 	Add a file to a project.
	# 	"""
	# 	pass

class CampaignUsers(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	campaign_id = db.Column(db.Integer(), db.ForeignKey('campaign.id', ondelete='CASCADE'))
	user_id = db.Column(db.Integer(), db.ForeignKey('user.id', ondelete='CASCADE'))

db.create_all()

# Setup Flask-User
db_adapter = SQLAlchemyAdapter(db,  User)       # Select database adapter
user_manager = UserManager(db_adapter, app)     # Init Flask-User and bind to app



@app.route("/")
@login_required
def home():
	if (not current_user.is_admin) and (not current_user.is_supervisor):
		if current_user.current_project:
			#redirect to the user's current project
			project=Campaign.query.filter(Campaign.id==current_user.current_project).first()
			return redirect(url_for('project_page',slug=project.slug,user_id=current_user.id))
		else:
			project=Campaign.query.filter(Campaign.users.any(id=current_user.id)).first()
			if project:
				#find the users first project and set that as current
				current_user.current_project=project.id
				db.session.commit()
				return redirect(url_for('project_page',slug=project.slug,user_id=current_user.id))
			else:
				#user has no projects at all, so go to the list to you can add one?
				return redirect(url_for('project_list'))
	else:
		return redirect(url_for('project_list'))
		
	workon=request.args.get('workon', False)
	if workon:
		current_user.current_project=int(workon)
		db.session.commit()
	my_projects=Campaign.query.filter(Campaign.users.any(id=current_user.id))
	return render_template("home.html",my_projects=my_projects)



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
				flash("Created a new project <code>%s</code>"%(campaign.name),"ok")
			except Exception as e:
				db.session.rollback()
				flash("Failed to create new project. Verify that the name and project slug do not exist yet.","error")
	return render_template("admin.html",users=User.query.all(),campaigns=Campaign.query.all())

@app.route("/status")
def status():
	return render_template("status.html",
		users=User.query.all(),
		campaigns=Campaign.query.all()
	)

@app.route("/profile")
@login_required
def profile_page():
	return render_template("profile.html")

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
	return render_template("project-list.html",project_list=current_projects)



@app.route("/projects/<slug>/",methods=["GET","POST"])
@login_required
def project_userlist(slug=None):
	"""
	Shows the main project view for supervisors. It has a list of users and links to enroll other users which are not participating in the project yet. It is also possible to update the basemap for the project here by uploading a zip file (which will be unzipped) or individual files into the project's basemap directory.

	If this view is requested by a student user, the user is redirected directly to the student's project page.
	"""
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	if current_user.is_student:
		return redirect(url_for('project_page',slug=project.slug,user_id=current_user.id))
	if request.method=="POST":
		f = request.files['uploadfile']
		if f:
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
				except Exception as e:
					flash("Zip file could not be extracted! Hint: %s"%(e),"error")
			flash("File <code>%s</code> was uploaded to the project basemap."%(f.filename),"ok")

	users=User.query.filter(User.campaigns.contains(project)).all()
	enrollable_users=User.query.filter(~User.campaigns.contains(project)).all()
	return render_template("project-userlist.html",project=project,users=users,enrollable_users=enrollable_users)



@app.route("/projects/<slug>/<user_id>/")
@login_required
def project_page(slug=None,user_id=None):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	return render_template("project.html",project=project,user=user)

@app.route("/projects/<slug>/<user_id>/wms")
def wmsproxy(slug=None,user_id=None):
	"""
	This view acts as a HTTP proxy for the WMS server. There are a few reasons for going through the trouble of making a proxy:

	- Due to same origin policy the GetFeatureInfo requests need to originate on the same host. By having having a proxy this is guaranteed and it is possible to switch WMS servers on the fly if the need arises.
	- Sometimes QGIS server (if CRS restrictions have not been set manually in the project preferences) will return in XML a list of hundreds of allowed CRSes for each layer. This seriously bloats the GetProjectInfo request. In this proxy we can manually limit the allowed CRSes to ensure the document does not become huge.
	- QGIS server does not support json responses! Since we are handling a lot of these WMS requests using JavaScript (also the GetFeatureInfo requests) it would be a lot easier, faster, and result in cleaner code, if the WMS server just returned JSON documents. Using this proxy we can add json support if the request argument FORMAT is set to "application/json", and do the conversion serverside with xmltodict. A JSONP callback argument is also supported.
	- We can camouflage the MAP parameter. This usually takes a full pathname to the map file. However, we dont want to reveal this to the world and let everybody mess about with it. Therefore we can override the MAP parameter in the proxy from the URL, that way the URL for a fieldwork WMS server will be /projects/fieldwork-demo/3/wms?<params> which is a lot neater than /cgi-bin/qgisserv.fcgi?MAP=/var/fieldwork-data/.....etc. There will be no MAP attribute visible to the outside in that case since it is added only on the proxied requests.
	- There are some opportunities for caching/compressing WMS requests at a later time if we use this method
	- We can limit access to the fieldwork data to only logged in users, or allow a per-project setting of who should be able to access the wms data.
	"""
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()

	import xmltodict
	requestparams=dict(request.args) #we need something which is mutable...
	#requestparams.pop("MAP") #don't send the map param
	requestparams.update({'MAP':project.basemap})

	jsonp=request.args.get("JSONP","")
	if(jsonp):
		requestparams.pop("JSONP") #never send a JSONP parameter to the qgis server
	if(request.args.get("FORMAT","")=="application/json"):
		requestparams.update({'FORMAT':"text/xml"}) #always request xml from qgis server
	if(request.args.get("INFO_FORMAT","")=="application/json"):
		requestparams.update({'INFO_FORMAT':"text/xml"}) #always request xml from qgis server
	r=requests.get(app.config["WMS_SERVER_URL"],params=requestparams)
	print r.url
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
def project_enroll(slug=None,user_id=None):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	project.enroll_user(user.id)
	flash("User <code>%s</code> has been enrolled in the fieldwork project %s"%(user.username,project.name),"ok")
	return redirect(url_for('project_userlist',slug=slug))

@app.route("/projects/<slug>/<user_id>/file",methods=["GET","POST","HEAD"])
@login_required
def project_file(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
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
					spatialite_file=os.path.join(userdata,"features.sqlite")
					excel_parser(upload_file,spatialite_file)
			flash("Upload and processing of file <code>%s</code> completed."%(f.filename),"ok")
		except Exception as e:
			flash("An error occurred during the upload. Hint: %s"%(e),"error")
	return redirect(url_for('upload',slug=slug,user_id=user_id))

@app.route("/projects/<slug>/<user_id>/data",methods=["GET"])
@login_required
def upload(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	attachments=project.attachments(user_id)
	features=project.features(user_id)
	return render_template("upload.html",project=project,user=user,attachments=attachments,features=features)

@app.route("/projects/<slug>/<user_id>/feedback")
@login_required
def project_feedback(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	return render_template("feedback.html",project=project,user=user)

@app.route("/projects/<slug>/<user_id>/collaborate")
@login_required
def project_collaborate(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	users=User.query.filter(User.campaigns.contains(project)).all()
	return render_template("collaborate.html",project=project,user=user,users=users)

@app.route("/projects/<slug>/<user_id>/maps")
@login_required
def project_maps(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	if not project.basemap:
		flash("No basemap has been uploaded by project administrator yet.","error")
	#project_toc=project.table_of_contents
	#return render_template("maps.html",project=project,user=user,toc=project_toc)
	return render_template("maps.html",project=project,user=user)

@app.route("/install")
def install():
	"""
		Install the fieldwork online app.

		Todo: only do this when there is nothing there yet! Make a check and otherwise just show an empty help page or something.

	"""
	messages=[]
	if User.query.count()==0:
		db.session.add(Role(name="administrator"))
		db.session.add(Role(name="supervisor"))
		db.session.add(Role(name="student"))
		db.session.commit()
		messages.append("Created <code>administrator</code>, <code>supervisor</code> and <code>student</code> roles.")

		admin = User(username='admin', fullname='Site Admin', email='kokoalberti@yahoo.com', active=True, password=user_manager.hash_password('admin'))
		admin.roles.append(Role.query.filter(Role.name=='administrator').first())
		admin.roles.append(Role.query.filter(Role.name=='supervisor').first())
		db.session.add(admin)
		messages.append("Created a user <code>admin</code>")

		supervisor = User(username='supervisor', fullname='Site Supervisor', email='k.alberti@uu.nl', active=True, password=user_manager.hash_password('supervisor'))
		supervisor.roles.append(Role.query.filter(Role.name=='supervisor').first())
		db.session.add(supervisor)
		messages.append("Created a user <code>supervisor</code>")

		student = User(username='student', fullname='Sam Student', email='k.alberti@students.uu.nl', active=True, password=user_manager.hash_password('student'))
		student.roles.append(Role.query.filter(Role.name=='student').first())
		db.session.add(student)
		db.session.commit()
		messages.append("Created a user <code>student</code>")

		campaign = Campaign(name="Fieldwork Online Demo Project",description="A fieldwork campaign for demonstration purposes. This project showcases basic functionality and lets you try out the interface.")
		campaign.users.append(admin)
		db.session.add(campaign)
		db.session.commit()
		messages.append("Created a fieldwork project called demo project.'")
	else:
		messages.append("There are already users defined in the database. Please delete the database and try again.")


	return render_template("install.html",messages=messages)


if __name__ == "__main__":
    app.run(debug=True)



