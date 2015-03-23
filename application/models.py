import os
import requests
import glob
import shutil
import json
import random
import subprocess
import datetime
import zipfile 
import xmltodict

from flask import Flask, render_template, request, redirect, abort, flash, send_file, send_from_directory, url_for, make_response, Response, jsonify

from flask.ext.user import UserManager, UserMixin, SQLAlchemyAdapter
from flask.ext.user import current_user, login_required, roles_required, UserMixin
from slugify import slugify

from application import app, db


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
        self.password=kwargs["password"]
        self.add_role("student")
    @property
    def is_supervisor(self):
        """
        Returns True is user is a supervisor, otherwise False. Used in
        templates to allow syntax like 'if user.is_supervisor'
        """
        return self.has_role("supervisor")
    @property
    def is_admin(self):
        """
        Returns True is user is an admin, False otherwise.
        """
        return self.has_role("administrator")
    @property
    def is_student(self):
        """
        Returns True is user is a student, False otherwise.
        """
        return self.has_role("student")
    @property
    def role_list(self):
        """
        Returns a list of role names that this user has. This allows for easy 
        looping in templates, but also to check a role using template syntax
        like 'if "supervisor" in user.role_list'. Maybe rename to role_names?
        """
        return [role.name for role in self.roles]

    def has_role(self,role_name):
        """
        Returns True if a user has a role with name <role_name>, False otherwise
        """
        for role in self.roles:
            if role.name==role_name:
                return True
        return False
    def add_role(self,role_name):
        """
        Adds the role whose matches <role_name> to the user if the user did not
        already have this role.

        Returns True if it was added, False otherwise.
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
        """
        Tries to enroll a user with a given <invite_key>.
        """
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
        Returns the project the user is currently working on.
        """
        pass
    @property
    def slug(self):
        """
        Returns a URL-safe slug of the user in the form <user.id>.<user.username>
        """
        return slugify("%i-%s"%(self.id,self.username))
    @property
    def current_projects(self):
        if current_user.is_admin:
            return Campaign.query.all()
        else:
            return Campaign.query.filter(Campaign.users.any(id=self.id)).all()

class BackgroundLayer(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    campaign_id = db.Column(db.Integer(), db.ForeignKey('campaign.id'))
    name = db.Column(db.String(255), nullable=True, unique=False)
    filename = db.Column(db.String(255), nullable=True, unique=False)
    description = db.Column(db.Text(), nullable=True, unique=False)
    is_default = db.Column(db.Boolean(), nullable=False, default=False)
    def __init__(self,campaign_id,name,filename):
        self.campaign_id=campaign_id
        self.name=name
        self.filename=filename

class Feedback(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('user.id'))
    campaign_id = db.Column(db.Integer(), db.ForeignKey('campaign.id'))
    map_state = db.Column(db.Text(), nullable=True, unique=False)
    map_view = db.Column(db.String(255), nullable=True, unique=False) #x,y,z
    map_marker =  db.Column(db.String(255), nullable=True, unique=False) #x,y
    comment_date = db.Column(db.DateTime(), nullable=False, default=db.func.now())
    comment_by = db.Column(db.Integer(), db.ForeignKey('user.id'))
    comment_by_user = db.relationship('User', lazy='joined', foreign_keys=comment_by)
    comment_parent = db.Column(db.Integer()) #not in use. for replying to comments
    comment_body = db.Column(db.Text(), nullable=True)
    comment_attachment = db.Column(db.String(255), nullable=True, unique=False) #maybe change to LargeBinary later? for now store as file on filesystem.
    include_map = db.Column(db.Boolean(), nullable=False, default=False)
    broadcast = db.Column(db.Boolean(), nullable=False, default=False) #not in use. for broadcasting to all enrolled users
    read_unread = db.Column(db.Boolean(), nullable=False, default=False) #not in use. for toggling a comment as read/unread
    def __repr__(self):
        return "Feedback!"
    @property
    def comment_age(self):
        delta=datetime.datetime.utcnow()-self.comment_date
        seconds=delta.seconds+(delta.days*24*3600)
        if seconds < 60:
            return "Less than one minute ago"
        if seconds < 3600:
            return "%d minutes ago"%(seconds//60)
        if seconds < 86400:
            return "%d hours ago"%(seconds//(60*60))
        else:
            #%a %d %B at %H:%M
            return self.comment_date.strftime("%d %B at %H:%M")
    def attachhed_files():
        """
        Return a list of files attached to this comment. Link through a feedback/file view of 
        some sort.
        """
        pass

class FeedbackReply(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    feedback_id = db.Column(db.Integer(), db.ForeignKey('feedback.id', ondelete='CASCADE'))
    #feedback = db.relationship('Feedback', secondary='feedback_id', backref=db.backref('replies',lazy='dynamic'))    
    feedback=db.relationship(Feedback,backref="replies")
    comment_date = db.Column(db.DateTime(), nullable=False, default=db.func.now())
    comment_by = db.Column(db.Integer(), db.ForeignKey('user.id'))
    comment_by_user = db.relationship('User', lazy='joined', foreign_keys=comment_by)    
    comment_body = db.Column(db.Text(), nullable=True)
    def __init__(self,comment_body,comment_by):
        self.comment_body=comment_body
        self.comment_by=comment_by
    @property
    def comment_age(self):
        delta=datetime.datetime.utcnow()-self.comment_date
        seconds=delta.seconds+(delta.days*24*3600)
        if seconds < 60:
            return "Less than one minute ago"
        if seconds < 3600:
            return "%d minutes ago"%(seconds//60)
        if seconds < 86400:
            return "%d hours ago"%(seconds//(60*60))
        else:
            #%a %d %B at %H:%M
            return self.comment_date.strftime("%d %B at %H:%M")
        
    
# Define Role model
class Role(db.Model):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)
    def __repr__(self):
        return self.name

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
            os.makedirs(os.path.join(basedir,"projectdata","backgroundlayers"))

    def __repr__(self):
        return "<Campaign: /campaigns/%s>"%(self.slug)
    @property
    def time_basemap(self):
        if self.basemap_version:
            return self.basemap_version
        else:
            #return a date well in the past so that now() is always newer
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
                        flash("Command: <code>%s</code>"%(" ".join(cmd)))
                    else:
                        flash("Failed to reload basemap data for user <code>%s</code>. The map update script returned status code <code>%d</code>."%(user.username,returncode),"error")
                        flash("Command: <code>%s</code>"%(" ".join(cmd)))
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
    @property
    def background_layers(self):
        """
        Returns a list of tif tiles in the project's backgroundlayers directory.
        """
        file_list=[]
        l=BackgroundLayer.query.filter_by(campaign_id=self.id).all()
        for layer in l:
            try:
                file_list.append({
                    'name':layer.name,
                    'file':layer.filename
                    })
            except:
                pass
        return file_list
    @property
    def background_layer_default(self):
        l=BackgroundLayer.query.filter_by(campaign_id=self.id).first()
        return l.name
    @property
    def background_layers_mapfile(self):
        return os.path.join(self.projectdata,"backgroundlayers","backgroundlayers.map")
    def background_layers_update(self):
        """
        Updates the backgroundlayers.map file with the currently uplaoded tif files.
        """
        backgroundlayers_mapfile=render_template("mapserver/backgroundlayers.map",project=self)
        with open(self.background_layers_mapfile,'w') as f:
            f.write(backgroundlayers_mapfile)
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
            #total_seconds() is new in python 2.7
            #seconds=delta.total_seconds()
            seconds=delta.seconds+(delta.days*24*3600)
            if seconds < 60:
                return "Less than one minute ago"
            if seconds < 3600:
                return "%d minutes ago"%(seconds//60)
            if seconds < 86400:
                return "%d hours ago"%(seconds//(60*60))
            else:
                #%a %d %B at %H:%M
                return self.time_lastactivity.strftime("%d %B at %H:%M")


db_adapter = SQLAlchemyAdapter(db,  User)       # Select database adapter
user_manager = UserManager(db_adapter, app)     # Init Flask-User and bind to app
