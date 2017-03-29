"""
Flask/SQLAlchemy/GeoAlchemy data model for the Fieldwork Online webapplication.

Todo:

* Clean up imports, remove stuff that we don't need anymore.
"""

import os
import requests
import glob
#import shutil
import json
import random
#import subprocess
import datetime
#import zipfile
#import xmltodict
#import time
import hashlib
import pyproj

from osgeo import gdal, osr

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape#,from_shape
from geoalchemy2.elements import WKTElement#, WKBElement
#from geoalchemy2.functions import ST_Envelope,ST_AsText

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSON

from flask import Flask, render_template, request, redirect, abort, flash, send_file, send_from_directory, url_for, make_response, Response, jsonify, escape

from flask.ext.user import UserManager, UserMixin, SQLAlchemyAdapter, current_user, login_required, roles_required
from flask.ext.mail import Mail, Message

from werkzeug import secure_filename

from slugify import slugify

from collections import defaultdict
from application import app, db

def generate_random_key(length=12, choices="abcdefghjkmnpqrstuvwxyz23456789", upper=False):
    """
    Generate a 'random' string for use in WMS urls and invite keys. Realize
    that this string is really pseudorandom, but good enough for us to create
    random looking keys with. Character choices exclude characters that can be
    confused when written down: 1 and i and l, 0 and O.
    """
    if upper==True:
        choices=choices.upper()
    random.seed()
    return ''.join(random.choice(choices) for _ in range(length))

def date_to_text(date, fallback_format="%d %B at %H:%M"):
    """
    Converts a date to a user friendly string describing the age of the date
    like "less than a minute ago" or "6 hours ago". When the date is older
    than 24 hours the actual date is returned with some slight formatting for
    brevity.

    Todo:

    * Improve this a bit to avoid things like "1 minutes ago"
    """
    delta = datetime.datetime.utcnow() - date
    seconds = delta.seconds+(delta.days*24*3600)
    if seconds < 60:
        return "Less than one minute ago"
    if seconds < 3600:
        return "%d minutes ago"%(seconds//60)
    if seconds < 86400:
        return "%d hours ago"%(seconds//(60*60))
    else:
        return date.strftime(fallback_format)


class User(db.Model, UserMixin):
    """
    The User model describes users of the web application. It extends
    UserMixin, which adds functionality for the Flask-Login extension.

    Todo:

    * Figure out if some of the functionality implemented in properties
      like is_student, role_list, and methods like has_role() is not already
      present in Flask-Login's UserMixin class. If so, it would be possible
      to replace some of the custom methods here.
    """
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean(), nullable=False, default=False)
    username = db.Column(db.String(50), nullable=False, unique=True)
    fullname = db.Column(db.String(50), nullable=True, unique=False, default='')
    password = db.Column(db.String(255), nullable=False, default='')
    email = db.Column(db.String(255), nullable=False, unique=True)
    confirmed_at = db.Column(db.DateTime())
    reset_password_token = db.Column(db.String(100), nullable=False, default='')
    roles = db.relationship('Role', secondary='user_roles', backref=db.backref('users', lazy='dynamic'))
    current_project = db.Column(db.Integer(), db.ForeignKey('campaign.id'),nullable=True)

    def __repr__(self):
        """
        Returns a text representation of this user. Shows the user's current
        project as well.
        """
        return "<User: %s CurrentProject: %s>"%(self.username,self.current_project)

    def __init__(self, **kwargs):
        """
        Create a new user. This is run when you create a new User instance
        using User() with the appropriate keyword arguments.
        """
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
        """
        Removes a role from a user.
        """
        role=Role.query.filter(Role.name==role_name).first()
        if role and self.has_role(role_name):
            self.roles.remove(role)
            db.session.commit()
            return True
        else:
            return False

    def enroll_with_invite_key(self,invite_key):
        """
        Enrolls the user in whatever project matches the provided <invite_key>.
        Returns True if a campaign with the invite key was found, False
        otherwise.
        """
        campaign=Campaign.query.filter_by(invite_key=invite_key).first()
        if campaign:
            campaign.enroll_user(self.id)
            return True
        else:
            return False

    @property
    def slug(self):
        """
        Returns a URL-safe slug of the user in the format:

        <user.id>-<user.username>

        For admin this would be something like "1-admin". It is mostly used in
        creating safe and unique directories on the filesystem to store user-
        data in.
        """
        return slugify("%i-%s"%(self.id,self.username))

    @property
    def current_projects(self):
        """
        Returns a list of projects accessible to this user. If the user is an
        admin, all projects in the site are returned, otherwise only those that
        the user is enrolled in.
        """
        if current_user.is_admin:
            return Campaign.query.all()
        else:
            return Campaign.query.filter(Campaign.users.any(id=self.id)).all()

    def last_comment_for(self, campaign_id):
        """
        Returns the date when this user last made a comment to username in the
        project specified by 'campaign_id'. We use this date to compare with
        the date when the user (student) last made a comment so we can show a
        link to signify that there are new comments for the supervisor to have
        a look at. Otherwise supervisors would have to visit each of their
        student's workspaces to see if there are any new comments. The function
        returns a defaultdict (a dictionary with a default value) with a
        default date far in the past. The dictionary key is the user id.

        Todo:

        * This is broken somehow and doesn't work properly. Find out what's
          wrong and fix it. The link which signifies that there are new
          comments/feedback in the workspace is located in the 'project' view.
          Uncommenting the Feedback query below breaks it. Otherwise the
          defaultdict is just always returned, meaning there are always new
          comments and the "new comments" icon is always shown. See
          project.html template near: <i class="fa fa-comments"></i>

        """
        feedback_for = defaultdict(lambda: datetime.datetime(2000, 1, 1, 12, 0, 0))
#        feedback=Feedback.query.filter_by(campaign_id=campaign_id,comment_by=self.id).group_by(Feedback.user_id,Feedback.id).order_by("comment_date asc").all()
#        for f in feedback:
#            feedback_for[f.user.username]=f.comment_date
        return feedback_for




class Feedback(db.Model):
    """
    The Feedback model stores all feedback (also referred to as comments) in
    the web application. There is an optional reference to another Feedback
    instance which can serve as a 'parent' comment. Any replies which are
    added on the Feedback page in a users workspace will have a parent. Any
    comments which are posted directly from the Maps page will not have a
    parent.
    """
    __tablename__ = 'feedback'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('user.id'))
    user = db.relationship('User', lazy='joined', foreign_keys=user_id)
    campaign_id = db.Column(db.Integer(), db.ForeignKey('campaign.id'))
    map_state = db.Column(db.Text(), nullable=True, unique=False) #pipe-separated list of layer names (layer|layer|layer)
    map_view = db.Column(db.String(255), nullable=True, unique=False) #comma-separarated x,y and zoom level: x,y,z
    map_marker =  db.Column(db.String(255), nullable=True, unique=False) #comma-separated x,y
    comment_date = db.Column(db.DateTime(), nullable=False, default=db.func.now())
    comment_by = db.Column(db.Integer(), db.ForeignKey('user.id'))
    comment_by_user = db.relationship('User', lazy='joined', foreign_keys=comment_by)
    comment_parent_id = db.Column(db.Integer(), db.ForeignKey('feedback.id')) #id of the comment parent
    comment_children = db.relationship("Feedback", backref=db.backref('parent', remote_side=[id])) #relationship to children (replies) of this comment
    comment_body = db.Column(db.Text(), nullable=True) #comment body
    comment_attachment = db.Column(db.String(255), nullable=True, unique=False) #not in use. for attaching a file to a comment.
    include_map = db.Column(db.Boolean(), nullable=False, default=False) #not in use. for comments without a map.
    broadcast = db.Column(db.Boolean(), nullable=False, default=False) #not in use. for broadcasting to all enrolled users
    read_unread = db.Column(db.Boolean(), nullable=False, default=False) #not in use. for toggling a comment as read/unread

    def __repr__(self):
        """
        Text representation of a Feedback instance.
        """
        return "<Feedback for user %d by user %d>"%(self.user_id,self.comment_by)

    @property
    def comment_age(self):
        """
        Returns a readible age of the comment using the date_to_text()
        function.
        """
        return date_to_text(self.comment_date)

    @property
    def num_of_replies(self):
        """
        Returns the number of replies that this comment has. The actual replies
        are accessible in self.comment_children.
        """
        return len(self.comment_children)

    @property
    def comment_body_truncated(self):
        """
        Returns a truncated comment body, cut off at 75 characters. This is
        used in the comment overview page where very long comments would mess
        up the formatting.
        """
        length = 75
        return self.comment_body[:length] + (self.comment_body[length:] and '...')

    @property
    def all_replies(self):
        """
        Return all the replies to this specific comment.

        Todo:

        * Errr wait.. how is this different from the self.comment_children
          relation defined in the data model? Figure out if this all_replies
          property is still used somewhere, otherwise delete it and just loop
          through the comment_children.
        """
        return Feedback.query.filter_by(comment_parent=self.id).order_by("comment_date asc").all()

class Role(db.Model):
    """
    The Role model stores the roles that users may have. The "initdb" function
    in the manage script is the only place where roles are created. Currently
    the application uses only "administrator", "supervisor", and "student"
    roles. Not a very exciting model.
    """
    __tablename__ = 'role'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)
    def __repr__(self):
        """
        Text representation of this role.
        """
        return "<Role %s>"%(self.name)

class UserRoles(db.Model):
    """
    The UserRoles model stores which users are assigned which roles. Absence
    of any role is usually interpreted as being a student. Also not a very
    exciting model.
    """
    __tablename__ = 'user_roles'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('user.id', ondelete='CASCADE'))
    role_id = db.Column(db.Integer(), db.ForeignKey('role.id', ondelete='CASCADE'))

class Campaign(db.Model):
    """
    The Campaign model (also referred to as a "Project" throughout the app)
    represents the fieldwork campaigns/projects available in the site.
    """
    __tablename__ = 'campaign'
    id =  db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=False, unique=False)
    slug = db.Column(db.String(50), nullable=False, unique=True)
    invite_key = db.Column(db.String(50), nullable=True)
    users = db.relationship('User', secondary='campaign_users', backref=db.backref('campaigns',lazy='dynamic'))
    basemap_version = db.Column(db.DateTime())
    allow_feedback = db.Column(db.Boolean(), nullable=False, default=True)
    allow_collaborate = db.Column(db.Boolean(), nullable=False, default=True)

    def __init__(self, name, description):
        """
        Creates a new project and only needs to be passed a name and a
        description. A slug is created from the name, a random invite key is
        created, and a directory structure on disk is made where project
        related data can be stored. Userdata is stored in the "userdata"
        subdirectory of a project. File uploads are stored in "attachments"
        and background layers in "backgroundlayers"
        """
        self.name=name
        self.description=description
        random.seed()
        self.invite_key=generate_random_key(length=6,upper=True)
        self.slug=slugify(name)
        basedir=self.basedir
        if not os.path.isdir(basedir):
            os.makedirs(basedir)
            os.makedirs(os.path.join(basedir,"userdata"))
            os.makedirs(os.path.join(basedir,"projectdata","map"))
            os.makedirs(os.path.join(basedir,"projectdata","attachments"))
            os.makedirs(os.path.join(basedir,"projectdata","backgroundlayers"))

    def __repr__(self):
        """
        Return a text representation of a campaign.
        """
        return "<Campaign: /campaigns/%s>"%(self.slug)

#    @property
#    def time_basemap(self):
#        if self.basemap_version:
#            return self.basemap_version
#        else:
#            #return a date well in the past so that now() is always newer
#            return datetime.datetime(2000, 1, 1, 12, 0, 0)

    @property
    def basedir(self):
        """
        Returns the base directory for this project.
        """
        return os.path.join(app.config["DATADIR"],"campaigns",self.slug)

    @property
    def projectdata(self):
        """
        Returns the project data directory for this project.
        """
        return os.path.join(app.config["DATADIR"],"campaigns",self.slug,"projectdata")

#    @property
#    def basemap(self):
#        """
#        Returns the filename of the basemap for this project. Returns False if no basemap has been uploaded.
#        """
#        projectfiles=glob.glob(os.path.join(self.basedir,"projectdata","map")+"/*.qgs")
#        try:
#            return projectfiles[0]
#        except:
#            return False

    @property
    def enrolled_users(self):
        """
        Returns the number of users enrolled in this project.

        Todo:

        * Find out where/if this is still used. Does it really matter? And
          should the property not be called num_of_enrolled_users then? Or just
          do len(self.users) in whatever view this is needed...
        """
        return len(self.users)

    def userdata(self,user_id):
        """
        Returns the userdata directory for a particular user in this fieldwork
        project. The directory is structured as:

        <project.basedir>/userdata/<user.slug>/

        Like:

        /var/wwwdata/fieldworkonline/projects/frankrijk-2015/userdata/1-admin/attachments (etc...)

        With subdirectories 'map' and 'attachments'. This is where user data
        related to a particular project is stored.
        """
        user = User.query.filter(User.id==int(user_id)).first()
        userdir = os.path.join(self.basedir,"userdata",user.slug)
        if not os.path.isdir(userdir):
            os.makedirs(userdir)
            os.makedirs(os.path.join(userdir,"map"))
            os.makedirs(os.path.join(userdir,"attachments"))
        return userdir

#    def basemap_for(self,user_id=None):
#        projectfiles=sorted(glob.glob(os.path.join(self.userdata(user_id),"map")+"/*.qgs"), key=os.path.getmtime)
#        try:
#            return projectfiles[-1]
#        except:
#            return False

#    def projectdata_for(self,user_id=None):
#        """
#        Returns a CampaignUsers object in which the configuration and other
#        data is stored for a user's enrollment in a project. For example when
#        the user was last seen online.
#
#        Todo:
#
#        * Find out if this is still used and whether it is necessary. I think
#          we usually get the appropriate CampaignUsers instance in the views
#          by just querying for it, but perhaps this is easier.
#        """
#        try:
#            return CampaignUsers.query.filter(CampaignUsers.campaign_id==self.id,CampaignUsers.user_id==user_id).first()
#        except Exception as e:
#            return None

#    def basemap_update(self,user_id=None):
#        """
#        Update the basemap for users enrolled in this project. If no user_id supplied the basemap is updated for all users enrolled in this project, otherwise only for the user provided. This option usually occurs when the user is first enrolled in a project, or when a user updates his data.
#
#        Actually updating the basemap is done by a standalone script "clone-qgis-fieldwork-project.py" which is located in the ~/scripts/ subdirectory of the fieldwork app. This script is called using subprocess and should return code 0 for success. Anyhting else means something went wrong. This action is done by a separate script to avoid having to use the QGIS API (which is a bit unstable sometimes) from within the web application. This way if the script crashes or whatever, it will just return status != 0 and we can report the error in the web app without breaking anything else.
#        """
#        flash("No longer updating basemap when using PostGIS features instead of sqlite","info")
#        return True
#
#        try:
#            users=[User.query.filter(User.id==int(user_id)).first()]
#        except:
#            users=self.users
#        if self.basemap:
#            for user in users:
#                target=self.userdata(user.id)
#                script=os.path.join(app.config["APPDIR"],"scripts","clone-qgis-fieldwork-project.py")
#                cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==self.id,CampaignUsers.user_id==user.id).first()
#                try:
#                    cmd=["/usr/bin/python",script,"--clone",self.basemap,"--target",target]
#                    child=subprocess.Popen(cmd, stdout=subprocess.PIPE)
#                    streamdata=child.communicate()[0]
#                    returncode=child.returncode
#                    if returncode==0:
#                        cu.time_basemapversion=db.func.now()
#                        db.session.commit()
#                        flash("Reloaded basemap data for user <code>%s</code>"%(user.username),"debug")
#                        flash("Command: <code>%s</code>"%(" ".join(cmd)),"debug")
#                    else:
#                        flash("Failed to reload basemap data for user <code>%s</code>. The map update script returned status code <code>%d</code>."%(user.username,returncode),"error")
#                        flash("Command: <code>%s</code>"%(" ".join(cmd)),"debug")
#                        flash("Script output: <code>%s</code>"%(streamdata),"debug")
#                except Exception as e:
#                    flash("Failed to reload basemap data for user <code>%s</code>. An exception occurred while trying to run the map update script. Hint: %s"%(user.username,e),"error")
#            return True
#        else:
#            flash("Basemap could not be updated because no basemap has been uploaded in this project.","error")
#            return False

    def enroll_user(self, user_id):
        """
        Enrolls a user specified by <user_id> in this fieldwork campaign.

        Todo:

        * We query CampaignUsers now with .count() to check how many there are,
          but it might be better to use .first() and then just check if
          enrollment is None rather than enrollment==0.
        """
        try:
            user = User.query.filter(User.id==int(user_id)).first()
            enrollment = CampaignUsers.query.filter(CampaignUsers.campaign_id==self.id,CampaignUsers.user_id==user.id).count()
            if enrollment==0:
                #user not yet enrolled...
                #userdir = self.userdata(user_id)
                self.users.append(user)
                db.session.commit()
                #self.basemap_update(user_id)
                flash("User <code>%s</code> has been successfully enrolled in the fieldwork project %s"%(user.username,self.name),"ok")
                return True
            else:
                #user already enrolled.
                flash("User <code>%s</code> is already enrolled in this fieldwork project %s"%(user.username,self.name),"ok")
                return True
        except Exception as e:
            flash("Failed to enroll user <code>%s</code> in the fieldwork project %s. Hint: %s"%(user.username,self.name,e),"error")
            return False

    def deroll_user(self,user_id):
        """
        Remove enrollment of a user in a project. At the moment the user's
        data directory is preserved.
        """
        try:
            user = User.query.filter(User.id==int(user_id)).first()
            enrollment = CampaignUsers.query.filter(CampaignUsers.campaign_id==self.id,CampaignUsers.user_id==user.id).all()
            if enrollment==None:
                flash("User was not enrolled in this project.","error")
            else:
                for e in enrollment:
                    db.session.delete(e)
                db.session.commit()
                flash("Removed enrollemnt","ok")
                return True
        except Exception as e:
            flash("An error occurred! Hint: %s"%(e),"error")
            return False

    @property
    def background_layer_default(self):
        """
        Returns the name of the default backgroun layer.
        """
        backgroundlayer = BackgroundLayer.query.filter_by(campaign_id=self.id).first()
        return backgroundlayer.name

    @property
    def background_layers_mapfile(self):
        """
        Returns the name of the mapserver configuration which contains the
        background layers available in this project.
        """
        return os.path.join(self.projectdata, "backgroundlayers", "backgroundlayers.map")

    @property
    def background_layers_wms_url(self):
        """
        Returns the URL of the WMS service where the backgroundlayers
        associated with this project may be found. Because we have only one
        mapfile for all the background layers in a specific project, this
        WMS url is a property of the project rather than the BackgroundLayer
        instance itself.
        """
        return app.config["MAPSERVER_URL"]+"?MAP=%s"%(self.background_layers_mapfile)

    @property
    def collaborate_layers(self):
        """
        Returns a list of unique safe_names that exist as ObservationLayers
        among all the users in the campaign.
        """
        collaboratelayers={}
        observationlayers=ObservationLayer.query.filter_by(campaign_id=self.id).all()
        for layer in observationlayers:
            if layer.safe_name not in collaboratelayers.keys():
                collaboratelayers[layer.safe_name]={"name":layer.name, "safe_name": layer.safe_name}
        return collaboratelayers

    def campaign_data_featurecollection(self, safe_name):
        """
        Returns a list of GEOJsons for each unique name in all observation
        layers in the campaign.
        To Do:
        -query all observationlayers with campaign_id=self.campaign_id
        -create a list of all unique names among these observationlayers,
            and a list of all observationlayers per name
        -jsonify each name and return the links for each of them.
        """
        layers=ObservationLayer.query.filter_by(campaign_id=self.id, safe_name=safe_name).all()
        features=[]
        for layer in layers:
            for feat in layer.observations:
                features.append(feat.as_dict())
        featurecollection={
            "type": "FeatureCollection",
            "features": features
        }
        return featurecollection

    def background_layers_update(self):
        """
        Updates the mapserver configuration file (backgroundlayers.map) file
        to match the background layers currently uploaded in the project.
        """
        try:
            backgroundlayers_mapfile = render_template("mapserver/backgroundlayers.map", project=self)
            with open(self.background_layers_mapfile, 'w') as f:
                f.write(backgroundlayers_mapfile)
        except Exception as e:
            flash("Could not update <code>backgroundlayers.map</code> in the %s project. Hint: %s"%(self.name, e), "error")
            return False
        else:
            return True


    def attachments(self,user_id):
        """
        Returns a list of attachments that the specified user has uploaded to
        this project. Use sorted(glob.glob(...), key=os.path.getmtime) to sort
        by modification time instead.

        Todo:

        * Is this still the best way? Seems like this code could be more
          concise.
        """
        file_list=[]
        files=sorted(glob.glob(os.path.join(self.userdata(user_id),"attachments")+"/*.*"))
        for f in files:
            try:
                (head,tail)=os.path.split(f)
                extension=os.path.splitext(f)[1].lower()
                if extension.endswith((".png",".jpg",".jpeg")): filetype="image"
                elif extension.endswith((".xls",".xlsx")): filetype="spreadsheet"
                elif extension.endswith((".doc",".docx",".pdf",".txt")): filetype="document"
                else: filetype="other"
                file_list.append({
                    'name':tail,
                    'type':filetype,
                    'extension':extension,
                    'size':os.path.getsize(f)
                })
            except Exception as e:
                pass
        return file_list

class CampaignUsers(db.Model):
    """
    The CampaignUsers model stores the enrollment of users in a particular
    fieldwork Campaign. This model stores the data related to a user in a
    campaign: things like when the user was last active. Whether a user is
    enrolled in a Campaign at all is determined by the presence of a
    CampaignUsers instance with a user_id of the user and the campaign_id of
    the campaign in question.
    """
    __tablename__ = 'campaign_users'
    id = db.Column(db.Integer(), primary_key=True)
    campaign_id = db.Column(db.Integer(), db.ForeignKey('campaign.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer(), db.ForeignKey('user.id', ondelete='CASCADE'))
    time_enrollment = db.Column(db.DateTime, nullable=False, default=db.func.now())
    time_basemapversion = db.Column(db.DateTime())
    time_lastactivity = db.Column(db.DateTime())
    wms_key = db.Column(db.String(50),nullable=True,default=generate_random_key)
    campaign=db.relationship(Campaign, backref="memberships")
    user=db.relationship(User,backref="memberships")
    def __repr__(self):
        """
        Text representation of a users enrollment.
        """
        return "<CampaignUser User %s enrolled in Campaign %s>"%(self.user.username, self.campaign.name)

    def update_lastactivity(self):
        """
        Updates the last activity of the user.

        Todo:

        * Figure out if this is in use still, otherwise delete is. Also, what
          does last activity mean? Its not updated when a user logs in, maybe
          when data is uploaded (then it should be called last_data_upload) or
          when they leave a comment? Hmm... Perhaps it is called after data
          or files are uploaded.
        """
        self.time_lastactivity = db.func.now()
        db.session.commit()

    @property
    def text_lastactivity(self):
        """
        Text representation of when data was last uploaded by the user in this
        project.
        """
        if not self.time_lastactivity:
            return "No data uploaded yet"
        else:
            return date_to_text(self.time_lastactivity)

    @property
    def last_post(self):
        """
        Returns the time when the user last posted a comment or a reply to
        another comment.
        """
        last_feedback = Feedback.query.filter_by(comment_by=self.user_id,campaign_id=self.campaign_id).order_by("comment_date desc").first()
        if last_feedback is None:
            return datetime.datetime(2000, 1, 1, 12, 00, 00)
        else:
            return last_feedback.comment_date

class CampaignUsersFavorites(db.Model):
    """
    The CampaignUsersFavorites (3x woordwaarde) model defines "favorites" for
    a user per project. This allows supervisors to pin users they are
    supervising as 'favorites', which then will show up on top of the list.
    This works a bit like pinning in e-mail applications. The user_id field
    defines the user which is is pinned. If an entry exists then it is pinned,
    if no entry exists then it is not pinned.
    """
    __tablename__ = 'campaign_users_favorites'
    id = db.Column(db.Integer(), primary_key=True)
    campaignusers_id = db.Column(db.Integer(), db.ForeignKey('campaign_users.id', ondelete='CASCADE'))
    campaignusers=db.relationship(CampaignUsers,backref="favorites")
    user_id = db.Column(db.Integer(), db.ForeignKey('user.id', ondelete='CASCADE'))

class BackgroundLayer(db.Model):
    """
    The BackgroundLayer model defines background layers for a project. These
    can be uploaded from the project page by supervisors and are added as back-
    grounds to the project maps, in addition to the Bing Maps layers for
    Road and Aerial. Serving of backgroundlayers occurs through mapserver, so
    that needs to be set up properly for the layers to be visible in the map.

    Todo:

    * Implement this properly so that new layers which are uploaded are stored
      and referenced propertly.

    * Add backref to a project (backgroundlayers)

    * Add an extent geom field. We can merge all these geoms to make a default
      view for the project area.
    """
    __tablename__ = 'background_layer'
    id = db.Column(db.Integer(), primary_key=True)
    campaign_id = db.Column(db.Integer(), db.ForeignKey('campaign.id'))
    campaign = db.relationship(Campaign, backref="backgroundlayers")
    name = db.Column(db.String(255), nullable=True, unique=False)
    filename = db.Column(db.String(255), nullable=True, unique=False)
    description = db.Column(db.Text(), nullable=True, unique=False)
    is_default = db.Column(db.Boolean(), nullable=False, default=False)
    is_enabled = db.Column(db.Boolean(), nullable=False, default=True)
    def __init__(self, filename):
        """
        Creates a new BackgroundLayer instance by passing it the filename of
        the uploaded file.
        """
        #Set some basic values
        self.filename = filename
        (head,tail) = os.path.split(filename)
        self.name = tail.split(".")[0]
        self.description = "this is a background layer"

        #Verify that the file is in fact a gdal raster
        ds = gdal.Open(self.filename)
        if ds is None:
            raise Exception("Unable to open the input file with gdal.Open()")
        else:
            #Check that the file is a geotiff file
            if ds.GetDriver().ShortName != 'GTiff':
                raise Exception("Dataset is not a GeoTIFF file.")
            #With three bands
            if ds.RasterCount != 3:
                raise Exception("Dataset does not have exactly 3 bands.")

            #And try and obtain the srs of the uploaded file in a try statement
            #because there are various things that can go wrong here.
            try:
                srs = osr.SpatialReference(wkt=ds.GetProjection())
                srs.Fixup()
                srs.AutoIdentifyEPSG()
                srid = int(srs.GetAuthorityCode(None))
                assert srid == 3857
            except:
                raise Exception("Dataset could not be identified as being projected in a pseudomercator projection with EPSG:3857.")

    @property
    def label(self):
        return self.description

class ObservationLayer(db.Model):
    """
    The ObservationLayer model defines a group of observations (i.e. a single
    sheet in an uploaded excel sheet with observations in it).
    """
    __tablename__="observation_layer"
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('user.id'))
    user = db.relationship(User, backref=db.backref('observations'))
    campaign_id = db.Column(db.Integer(), db.ForeignKey('campaign.id'))
    campaign = db.relationship(Campaign, backref=db.backref('observations'))
    name = db.Column(db.String(255), nullable=True, unique=False)
    safe_name = db.Column(db.String(255), nullable=True, unique=False)
    def __init__(self,user_id,campaign_id,name,safe_name):
        """
        Create a new ObservationLayer
        """
        self.user_id=user_id
        self.campaign_id=campaign_id
        self.name=name
        self.safe_name=safe_name

    @property
    def slug(self):
        """
        Todo:

        * Check if this is used. Its probably better to use the safe_name
          attribute instead of this slug.
        """
        return slugify(self.name)

    @property
    def color(self):
        """
        The color property creates a random color from the name by hashing the
        name, running it through hexdigest, and taking the first six
        characters. This is then a valid html color like #fc3fc3 which can be
        used to ensure that the colors that the dots of the different map
        layers have are somewhat unique.
        """
        return '#'+hashlib.md5(self.name).hexdigest()[0:6]

    @property
    def num_observations(self):
        """
        Returns the number of observations in this ObservationLayer.
        """
        return len(self.observations)

    @property
    def download_link(self):
        """
        Returns a download link for this ObservationLayer which points to the
        'project_data_download' view, which is publically accessible.
        """
        cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==self.campaign_id, CampaignUsers.user_id==self.user_id).first()
        return url_for('project_data_download', project_key=cu.wms_key, safe_name=self.safe_name, _external=True)

    def as_featurecollection(self):
        """
        Returns a GeoJSON featurecollection of all the points in this
        ObservationLayer.

        Todo:

        * Find out if this can be done directly in PostGIS rather than call
          as_dict() on each Observation in the ObservationLayer.

        * Find out if other data formats can be integrated in a better way. Of
          course we can create as_featurecollection() or as_gml() or
          as_shapefile() functions, but perhaps there is a more organized way
          of doing this.
        """
        features=[]
        for feat in self.observations:
            features.append(feat.as_dict())
        featurecollection={
            "type": "FeatureCollection",
            "features": features
        }
        return featurecollection

class Observation(db.Model):
    """
    The Observation model represents a single Observation (i.e. a row in an
    uploaded excel sheet) which is part of an ObservationLayer. The relation-
    ship between the two is accessible as:

    observation.observationlayer -> get the observationlayer to which this
                                    observation belongs

    observationlayer.observations -> get the observations in the Observation-
                                     Layer instance.

    Todo:

    * Better error handling. Raise an exception (or skip) when the creation
      fails or if the dict that is passed upon intialization is faulty.

    * Automatically convert any points to lat-lng? The geometry in the
      database is fixed now to EPSG:4326, so all points should be stored in
      that CRS as well. It would be possible to remove the srid and allow
      storage of points without a coordinate system implicitly attached, but
      that would probably make things more difficult down the road when you're
      trying to get your geodata out of the database again.

    * Explore alternative ways of getting this data out and converting it to
      another format. Now we use the as_dict to make a GeoJSON-like dictionary
      of the point and its properties, but perhaps this can also be done using
      PostGIS functionaltiy. Look into PostGIS ST_AsGeoJSON() functions or
      ST_AsGML, and figure out what would be a good way to implement this here.
    """
    __tablename__="observation"
    id = db.Column(db.Integer(), primary_key=True)
    observationlayer_id = db.Column(db.Integer(), db.ForeignKey('observation_layer.id', ondelete='CASCADE'))
    observationlayer=db.relationship(ObservationLayer,backref=db.backref('observations', cascade="all, delete-orphan"))
    geom = db.Column(Geometry(geometry_type='POINT', srid=4326))
    properties = db.Column(JSON, nullable=True)
    def __init__(self, point=None):
        """
        Create a new Observation. It requires a dictionary 'point' to be
        passed which has the following keys:

        x -> x coordinate
        y -> y coordinate
        epsg -> code of the coordinate ref sys
        properties -> a dictionary of properties of this point. this will be
                      stored in the Observations' properties field, which is
                      a JSON field capable of storing flexible data.

        Because all points (possible with many different coordinate systems
        are all stored in a single PostGIS table, we convert them here to
        wgs84 lat-lng coordinates.
        """
        x = point['x']
        y = point['y']
        srid = point['epsg']

        projection = pyproj.Proj("+init=EPSG:%d"%(point['epsg']))
        if point['epsg'] != 4326:
            (x, y) = projection(x, y, inverse=True)
            srid = 4326

        self.geom=WKTElement('POINT(%.7f %.7f)'%(x,y), srid=srid)
        self.properties=json.dumps(point['properties'])

    def as_dict(self):
        """
        Returns the point as a GeoJSON-point-like dictionary. This dict can
        be plugged into some sort of JSON converter (like Flask's jsonify())
        and a nice GeoJSON feature should come rolling out.
        """
        pt=to_shape(self.geom)
        return {
            "type":"Feature",
            "geometry":{"type": "Point", "coordinates": [pt.x, pt.y]},
            "properties":json.loads(self.properties)
        }

db_adapter = SQLAlchemyAdapter(db,  User)
user_manager = UserManager(db_adapter, app)
mail = Mail(app)
