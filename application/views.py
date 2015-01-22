import os
import requests
import glob
import shutil
import json
import random
import subprocess
import datetime


from flask import Flask, render_template, request, redirect, abort, flash, send_file, send_from_directory, url_for, make_response, Response
from flask.ext.mail import Mail
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.user import current_user, login_required, roles_required, UserManager, UserMixin, SQLAlchemyAdapter
from slugify import slugify

from application import app
from .models import * 

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


