"""
Flask views for the Fieldwork Online web application
"""
from application import app
from .models import *

@app.route("/")
@login_required
def home():
    """
    The home view is not really a proper view but just redirects the user to
    the right place in more or less the following order:

    * Not logged in? Go to signup/login page. The redirect happens automa-
      tically because of the @login_required decorator.

    * If the current user is not working on a project
      (current_user.current_project is empty) then redirect to settings page
      so he can pick a project.

    * If you are working on a project, and you're not an admin or supervisor
      then go to the project overview page (workspace) where you can select
      data, maps, etc.

    * If you are working on a project, and you're an admin or supervisor then
      do the project page where you can see all the enrolled users, and where
      you can check out their workspaces.

    """
    if not current_user.current_project:
        return redirect(url_for('settings'))
    else:
        project=Campaign.query.filter(Campaign.id==current_user.current_project).first()
        if (project) and (not current_user.is_admin) and (not current_user.is_supervisor):
            #user is not an admin and not a supervisor
            return redirect(url_for('project_overview',slug=project.slug,user_id=current_user.id))
        elif (project) and ((current_user.is_admin) or (current_user.is_supervisor)):
            return redirect(url_for('project',slug=project.slug))
        else:
            return redirect(url_for('settings'))

@app.route("/admin", methods=["GET","POST"])
@login_required
@roles_required("administrator")
def admin():
    """
    The admin view is available only to administrators (see @roles_required
    decorator) and lets admin users:

    * Create new projects (action=project_create)

    * View existing projects and the invitation keys for those projects

    * View registered users and add/remove roles from them (action=rem_role or
      action=add_role)

    Todo:

    * GET should ideally not be used to modify server side state. Maybe move
      this add/remove role stuff to a different view accessible at:

      /admin/<username>/<role_name>/toggle
      /admin/<username>/<role_name>/add (or remove)

      And redirect back to the admin view using redirect(url_for('admin', ... ))

    """
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

@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    """
    The settings view lets logged in users (with all roles):

    * View their own settings

    * Choose a fieldwork project (that they're enrolled in) to work on. This
      will set the user's current_project.

    * Use an invite key (which would be given to the user by a teacher or
      supervisor) to enroll themselves in a project.
    """
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

@app.route("/manual/",methods=["GET","POST"])
@login_required
def manual():
    """
    View which displays the user manual for the website. There is no logic
    here, just render the manual.html template and that's it.
    """
    return render_template("manual.html")

@app.route("/projects/",methods=["GET","POST"])
@login_required
def project_list():
    """
    The project_list view is no longer in use. Accessing the "projects" page
    implies that you don't know what project you want to work on, so redirect
    the user to the settings page where he can pick a project to work on.
    """
    flash("You can choose a project to work on from your settings page.","info")
    return redirect(url_for('settings'))

@app.route("/projects/<slug>/",methods=["GET","POST"])
@login_required
def project(slug=None):
    """
    The project view is the "homepage" of a certain fieldwork project/
    campaign. It has a list of users and links to enroll other users which are
    not participating in the project yet.

    Note! This view is available only to supervisor or administrative users! A
    student user is redirected automatically to their workspace page on the
    "maps" view. We don't use the @roles_required decorator here because that
    would give a permission denied error rather than redirect the user to their
    workspace page.

    Supervisors and admins can use this view to:

    * Upload background maps for this project.

    * Manually enroll users.

    * View workspaces of enrolled users.

    Todo:

    * The code in this view is a bit of a mess. Refactor and clean it up a bit.

    * Uploading of zip files is no longer necessary if we're not using QGIS
      anymore. Remove that as well.

    * Letting supervisors know that a new comment has been posted using a
      comment icon is not working properly. It uses the last_comment_for()
      method on a user, but needs fixing.

    """

    #Fetch the project and the campaign user
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    cu = CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id, CampaignUsers.user_id==current_user.id).first()

    #Set the user's current_project to this project, and commit the change.
    current_user.current_project = project.id
    db.session.commit()

    #Redirect the user if they're not an admin or supervisor
    if not current_user.is_admin and not current_user.is_supervisor:
        return redirect(url_for('project_maps', slug=project.slug, user_id=current_user.id))

    #If the request method is POST we're probably trying to upload a file
    #like a basemap to the project.
    if request.method=="POST":
        f = request.files['uploadfile']
        filename = os.path.join(project.projectdata, "backgroundlayers", secure_filename(f.filename))
        
        #Create the new layer with the uploaded file.
        try:
            #Always delete any backgroundlayers which share the same filename.        
            BackgroundLayer.query.filter(BackgroundLayer.filename == filename).delete()
            #Save the uploaded file
            f.save(filename)
            #Create the new background layer using the new file
            backgroundlayer = BackgroundLayer(filename)
            #Add it to the project
            project.backgroundlayers.append(backgroundlayer)
            #Update the project's backgroundlayers.map mapserver configuration file
            project.background_layers_update()            
            #Commit changes
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash("Failed to create background layer from file. Hint: %s"%(e),"error")
        else:
            flash("Added background layer %s"%(backgroundlayer.name),"ok")
            

    #If the request method is GET it depends a little bit. If there is an
    #"action" variable we need to actually do something like enroll or toggle
    #a user. If there is no action variable we do the default thing, which is
    #render the template with a list of users, an upload form, and a bunch of
    #buttons.
    if request.method=="GET":
        if request.args.get("action","")=="enroll" and request.args.get("user_id","") != "":
            project.enroll_user(request.args.get("user_id",""))
            return redirect(url_for('project',slug=project.slug))
        if request.args.get("action","")=="deroll" and request.args.get("user_id","") != "":
            project.deroll_user(request.args.get("user_id",""))
            return redirect(url_for('project',slug=project.slug))
        if request.args.get("action","")=="toggleflag" and request.args.get("user_id","") != "":
            try:
                if cu==None:
                    flash("You are not enrolled in this project, therefore it is not possible to flag users.","error")
                else:
                    user=User.query.filter(User.id==int(request.args.get("user_id",""))).first()
                    cuf=CampaignUsersFavorites.query.filter(CampaignUsersFavorites.campaignusers_id==cu.id).filter(CampaignUsersFavorites.user_id==user.id).first()
                    if cuf==None:
                        #make a new entry
                        cu.favorites.append(CampaignUsersFavorites(user_id=user.id))
                        flash("Flagged user <code>%s</code>"%(user.username),"info")
                    else:
                        db.session.delete(cuf)
                        flash("Unflagged user <code>%s</code>"%(user.username),"info")
                    db.session.commit()
            except Exception as e:
                flash("Something went wrong adding favorite: Hint: %s"%(e))
            return redirect(url_for('project',slug=project.slug))

    #No action was defined. Fetch the students and supervisors, and just render
    #the project.html template to show the overview of the project.

    #users=User.query.filter(User.campaigns.contains(project)).all()
    #role_student=Role.query.filter(Role.name=='student').first()
    role_supervisor=Role.query.filter(Role.name=='supervisor').first()
    role_admin=Role.query.filter(Role.name=='administrator').first()

    students=User.query.\
        filter(User.campaigns.contains(project)).\
        filter(~User.roles.contains(role_supervisor)).\
        filter(~User.roles.contains(role_admin))

    supervisors=User.query.\
        filter(User.campaigns.contains(project)).\
        filter(User.roles.contains(role_supervisor)|User.roles.contains(role_admin)).all()

    enrollable_users=User.query.filter(~User.campaigns.contains(project)).all()
    backgroundlayers=BackgroundLayer.query.filter_by(campaign_id=project.id).all()
    comments=current_user.last_comment_for(campaign_id=project.id)

    #
    #todo: fix if cu==None
    #
    favorite_user_ids=[]
    if cu != None:
        favorite_user_ids=[cuf.user_id for cuf in cu.favorites]

    students_flagged=[]
    students_notflagged=[]
    if len(favorite_user_ids)>0:
        students_flagged=students.filter(User.id.in_(favorite_user_ids)).all()
        students_notflagged=students.filter(~User.id.in_(favorite_user_ids)).all()
    else:
        students_notflagged=students.all()

    students_all=[]
    students_all.extend(students_flagged)
    students_all.extend(students_notflagged)
    return render_template("project.html", project=project, supervisors=supervisors, students=students_all, enrollable_users=enrollable_users, backgroundlayers=backgroundlayers,comments=comments,favorite_user_ids=favorite_user_ids)

@app.route("/projects/<slug>/backgroundlayers/<int:backgroundlayer_id>")
@login_required
@roles_required("administrator")
def backgroundlayer_preview(slug=None, backgroundlayer_id=None):
    """
    Shows a simple preview and debug information on a background layer.
    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    backgroundlayer = BackgroundLayer.query.filter_by(id=backgroundlayer_id).first_or_404()
    
    #Check if mapserver is reachable.
    mapserver_request = requests.get(app.config["MAPSERVER_URL"])
    return render_template("backgroundlayer_preview.html", project=project, backgroundlayer=backgroundlayer, mapserver_request=mapserver_request)

@app.route("/projects/<slug>/<user_id>/")
@login_required
def project_overview(slug=None, user_id=None):
    """
    The project overview view is not really used at the moment because users
    are always viewing the data, maps, or comments and feedback page. This
    view could be used later perhaps to show an overview of the project to
    student users.
    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)
    return render_template("project/overview.html", project=project,user=user)

@app.route("/projects/<slug>/<user_id>/maps")
@login_required
def project_maps(slug, user_id):
    """
    The project_maps view shows a table with the observation layers and the
    background layers, as well as an OpenLayers map with the user's
    observations. Most of the magic here is happening client side in the
    JavaScript code.
    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()
    cu = CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id, CampaignUsers.user_id==user.id).first_or_404()

    #Ensure you can only see your own data, unless you're an admin or supervisor.
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)

    observationlayers = ObservationLayer.query.filter_by(user_id=user_id, campaign_id=project.id).all()
    return render_template("project/maps.html", observationlayers=observationlayers, project=project, user=user)

@app.route("/projects/<slug>/<user_id>/maps2")
@login_required
def project_maps2(slug, user_id):
    """
    The project_maps view shows a table with the observation layers and the
    background layers, as well as an OpenLayers map with the user's
    observations. Most of the magic here is happening client side in the
    JavaScript code.
    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()
    cu = CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id, CampaignUsers.user_id==user.id).first_or_404()

    #Ensure you can only see your own data, unless you're an admin or supervisor.
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)

    observationlayers = ObservationLayer.query.filter_by(user_id=user_id, campaign_id=project.id).all()
    return render_template("project/maps2.html", observationlayers=observationlayers, project=project, user=user)

@app.route("/projects/<slug>/<user_id>/feedback",methods=["GET","POST"])
@login_required
def project_feedback(slug, user_id):
    """
    The project_feedback view does one of two things depending on the request
    method:

    POST: Create a new Feedback instance and save it to the database. The forms
          for posting feedback are aimed at this view.

    GET:  Redirect the user to the project_feedback_detail view for the latest
          feedback item in the database. If there is no feedback found at all,
          render an empty template and flash() an error message.
    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()

    #Ensure you can only see your own data, unless you're an admin or supervisor.
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)

    cu = CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first_or_404()

    #POSting here means we want to create a new comment/feedback instance
    if request.method=="POST":

        #The comment_parent indicates the feedback parent item. All new feedback
        #does not have a parent (it will be None) and all replies will have
        #another Feedback instance as a parent.
        try: comment_parent=Feedback.query.get(int(request.form.get('comment_parent','')))
        except: comment_parent=None

        try:
            #Try to add the feedback to the database.
            feedback = Feedback(
                user_id=user.id,
                campaign_id=project.id,
                comment_by=current_user.id,
                comment_body=request.form.get('comment_body',''),
                parent=comment_parent,
                map_state=request.form.get('map_state',''),
                map_view=request.form.get('map_view',''),
                map_marker=request.form.get('map_marker','')
            )
            db.session.add(feedback)
            db.session.commit()
        except Exception as e:
            #Rollback if there is a screwup
            db.session.rollback()
            return jsonify(status="FAIL",message="Something went wrong trying to add feedback. Hint: %s"%(e)),500
        else:
            #If there is no screwup, either show an OK message in JSON, or
            #redirect the user to that specific comment parent.
            if comment_parent:
                #if this is a reply from the comment detail page, redirect back to it.
                return redirect(url_for('project_feedback_detail', slug=project.slug, user_id=user.id, comment_id=comment_parent.id))
            else:
                #otherwise just return a json ok reply.
                return jsonify(status="OK",message="Feedback posted!"),200

    #GETting this redirects you to the most recent feedback item.
    if request.method=="GET":
        #Get feedback, order by comment_date, get the first item.
        feedback = Feedback.query.filter_by(user_id=user.id, campaign_id=project.id).order_by("comment_date desc").first()
        if not feedback:
            #If the doesn't exist, flash an error message
            flash("No feedback has been left in this project yet.","info")
            return render_template("project/empty.html")
        else:
            #Or redirect the user if we've found something.
            return redirect(url_for('project_feedback_detail', slug=project.slug, user_id=user.id, comment_id=feedback.id))


@app.route("/projects/<slug>/<user_id>/feedback/<int:comment_id>",methods=["GET","POST"])
@login_required
def project_feedback_detail(slug, user_id, comment_id):
    """
    View for comment details. If the comment is in fact a reply to another
    comment (i.e. it has a parent) then redirect the user to that detail page.
    If the comment does not have a parent, render it (along with the map and
    any possible replies) using the project/feedback.html template.
    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()
    feedback = Feedback.query.filter_by(id=comment_id).first_or_404()
    if feedback.parent:
        #If the user is requesting a comment which is a reply to another comment,
        #then redirect straight to the parent comment's page.
        return redirect(url_for('project_feedback_detail', slug=project.slug, user_id=user.id, comment_id=feedback.parent.id))
    else:
        #If the comment does not have a parent, render the project/feedback.html
        #template with the appropriate content.
        recentcomments = Feedback.query.filter_by(user_id=user.id, campaign_id=project.id, parent=None).order_by("comment_date desc").all()
        return render_template("project/feedback.html", project=project, user=user, feedback=feedback, recentcomments=recentcomments)

@app.route("/projects/<slug>/<user_id>/data",methods=["GET"])
@login_required
def project_data(slug,user_id):
    """
    The project data view shows a list of ObservationLayers for this user in
    this project, and a list of files that have been uploaded by the user in
    this project. The template additionally shows an upload form in which
    multiple files can be uploaded.

    The actual file upload is not handled in this view, but the files are
    POSTed to the project_file view at /projects/<slug>/<user_id>/file, where
    Excel sheets are turned into point databases, and other files are just
    stored locally.
    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)
    attachments = project.attachments(user_id)
    observationlayers = ObservationLayer.query.filter_by(user_id=user_id, campaign_id=project.id).all()
    return render_template("project/data.html",project=project, user=user, attachments=attachments, observationlayers=observationlayers)

@app.route("/projects/<slug>/<user_id>/data/<safe_name>.geojson",methods=["GET"])
@login_required
def project_data_layer(slug,user_id,safe_name):
    """
    The project_data_layer view serves a GeoJSON featurecollection of all the
    points and attributes found in a particular observationlayer (defined by
    its safe_name). This geojson file is used by the OpenLayers map to display
    the user's observations as well. The GeoJSON is generated by the
    "as_featurecollection()" method of the ObservationLayer instance.

    Todo:

    * Technically this view is not necessary, as we can also link directly to
      the project_data_download view without the need to be logged in then.
      The mapping interface too should be able to load in GeoJSON files from
      the project_data_download view as well rather than this one which
      requires the user to be logged in.

    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()
    layer = ObservationLayer.query.filter_by(safe_name=safe_name, user_id=user.id, campaign_id=project.id).first_or_404()
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)
    return jsonify(layer.as_featurecollection()),200

@app.route("/<string:project_key>/<string:safe_name>.geojson",methods=["GET"])
def project_data_download(project_key, safe_name):
    """
    The project_data_download view is similar in functionality to the
    project_data_layer view, except that the URL used to access it is
    different, and that no @login_required decorator is present. As such, this
    view can be used for external applications which cannot log in to the
    Fieldwork Online application. The "project_key" variable is stored in the
    CampaignUsers model and is a random string, allowing this users' data to
    be downloaded from a URL like:

    /7j7c3pafxekg/fwo_netherlands_airports.geojson

    Todo:

    * Other formats could be added here as well, perhaps using a different
      route like /<string:project_key>/<string:safe_name>/<format>, allowing
      external parties or scripts to download your data like:

      /7j7c3pafxekg/fwo_netherlands_airports/shapefile

      or:

      /7j7c3pafxekg/fwo_netherlands_airports/spatialite

      Which would then show a download prompt with the data you're requested.
      Nice to do if there is some time somewhere. Don't forget to update the
      references to this url that are in templates with
      url_for('project_data_download' ... ).
    """
    cu = CampaignUsers.query.filter(CampaignUsers.wms_key==project_key).first_or_404()
    project = Campaign.query.get(cu.campaign_id)
    user = User.query.get(cu.user_id)
    layer = ObservationLayer.query.filter_by(safe_name=safe_name, user_id=user.id, campaign_id=project.id).first_or_404()
    return jsonify(layer.as_featurecollection()),200

@app.route("/projects/<slug>/<user_id>/data/map-layers.json", methods=["GET"])
@login_required
def project_data_maplayers(slug, user_id):
    """
    Returns a JSON document containing an array with the map layers that are
    shown in the OpenLayers map. This document is fetched by client-side
    JavaScript (see fieldworkonline-map.js) and then parsed to make proper
    layers for the OpenLayers map.
    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()

    #Ensure you can only see your own data, unless you're an admin or supervisor.
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)

    observationlayers = ObservationLayer.query.filter_by(user_id=user_id, campaign_id=project.id).all()

    #Create a layers array containing a dict for each layer.
    layers=[]
    layers.append({
        'name':'map',
        'label':'Mapquest Roads',
        'type':'background'
    })
    layers.append({
        'name':'sat',
        'label':'Mapquest Satellite',
        'type':'background'
    })
    
    for backgroundlayer in project.backgroundlayers:
        layers.append({
            'name':backgroundlayer.name,
            'label':backgroundlayer.name,
            'type':'wms',
            'attributes':{
                'mapserver_url':app.config["MAPSERVER_URL"],
                'mapserver_layer':backgroundlayer.name,
                'mapserver_mapfile':project.background_layers_mapfile
            }
        })
        
    for observationlayer in observationlayers:
        layers.append({
            'name':observationlayer.safe_name,
            'label':observationlayer.name,
            'type':'geojson',
            'attributes':{
                'url':url_for('project_data_layer', slug=project.slug, user_id=user.id, safe_name=observationlayer.safe_name),
                'color':observationlayer.color
            }
        })
    return jsonify(layers=layers),200


@app.route("/projects/<slug>/<user_id>/collaborate")
@login_required
def project_collaborate(slug,user_id):
    """
    The project_collaborate view is intented to provide some basic
    functionality which lets users share or export the data they're uploaded
    into the Fieldwork Online application. The actual code for doing this is
    usually in other views (like the geojson download), but this page serves
    as an easy to understand overview.

    Todo: (several ideas for improvement)
    * Make a "download campaign_data" link, where all campaign data is shown
      per theme and downloadable as GEOJson.

    * Make a "download all your data" link, which makes a zipfile of all your
      data and redirects the user to some sort of download view for it.

    * Make a "download as shapefile/spatialite/? format for your observation
      data. Once this is implemented in the project_data_download view a link
      can be added here quite easily.

    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()
    cu = CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first_or_404()

    #Ensure you can only see your own data, unless you're an admin or supervisor.
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)

    observationlayers = ObservationLayer.query.filter_by(user_id=user_id, campaign_id=project.id).all()
    return render_template("project/collaborate.html", project=project, user=user, cu=cu, observationlayers=observationlayers)

@app.route("/projects/<slug>/<user_id>/file",methods=["GET","POST","HEAD"])
@login_required
def project_file(slug,user_id):
    """
    The project_file view actually handles the uploading (POST) and downloading
    (GET) of files in a user's project workspace. For POST requests:

    * Save the file in the userdata directory (project.userdata(user.id))

    * If the file is an excel file, import "excel_parser" from utils, and run
      it on the excel file. This will turn the sheets into a bunch of
      observationlayers which are then committed to the database.

    For GET or HEAD requests:

    * If you're GETting an image file with the png, jpg, or jpeg extension,
      serve it by returning an image.

    * If it's not an image, use Flask's send_from_directory() with the
      as_attachment keyword argument to serve it as a download. The browser
      will show a download dialog in this case.

    * A HEAD request can be used to check if the file even exists or not,
      without sending all the data.

    Todo:

    * Turning the output of excel_parser() into Observations and
      ObservationLayers is still a bit messy. This could be cleaned up a little
      better.

    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()
    cu = CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first_or_404()

    #Ensure you can only see your own data, unless you're an admin or supervisor.
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)

    #Fetch the userdata directory and store it in the userdata variable. This
    #directory is where all the files will be uploaded.
    userdata = project.userdata(user.id)

    #GET or HEAD requests serve data
    if request.method=="HEAD" or request.method=="GET":
        filename=request.args.get("filename","")
        if filename != "":
            as_attachment = True if not filename.lower().endswith((".png",".jpg",".jpeg")) else False
            return send_from_directory(os.path.join(userdata,"attachments"), filename, as_attachment=as_attachment)

    #POST requests store data
    if request.method=="POST":
        try:
            print "import excel parser"
            from utils import excel_parser
            print "import excp ok!"
            f = request.files['file']
            if f:
                print "f found"
                upload_file=os.path.join(userdata,"attachments",f.filename)
                print "file ing as %s"%(upload_file)
                f.save(upload_file)
                print "file saved as %s"%(upload_file)
                if f.filename.endswith((".xls",".xlsx")):
                    #spatialite_file=project.features_database(user_id)

                    observations=excel_parser(upload_file)
                    for observation_layer in observations:
                        title = observations[observation_layer]['title']
                        points = observations[observation_layer]['observations']
                        #first delete any other observationlayers with this name
                        #deleted=ObservationLayer.query.filter_by(user_id=user_id,campaign_id=project.id,name=title).delete()
                        safe_name = observation_layer
                        deleted = ObservationLayer.query.filter_by(user_id=user_id,campaign_id=project.id,safe_name=safe_name).delete()
                        #flash("Deleted %d existing layer"%(deleted))
                        #db.session.delete(observationlayers)
                        db.session.commit()



                        layer = ObservationLayer(user.id, project.id, title, safe_name)
                        for point in points:
                            layer.observations.append(Observation(point))

                        db.session.add(layer)
                        db.session.commit()


                    #print observations
                    #project.basemap_update(user_id)


                    cu.update_lastactivity()

                flash("Upload and processing of file <code>%s</code> completed."%(f.filename),"ok")
        except Exception as e:
            flash("An error occurred during the upload. Hint: %s"%(e),"error")
    return jsonify(status="OK",message="File uploaded and processed!"),200

@app.route("/projects/<slug>/<user_id>/enroll")
@login_required
@roles_required("administrator")
def project_enroll(slug=None,user_id=None):
    """
    The project enroll view allows administrator users to enroll users by
    using a direct link to /projects/<slug>/<user_id>/enroll.

    Todo:

    * Check if this is being used anywhere, it seems not to be the case as
      enrollments and derollments are handled in the "project" view. So either
      get rid of those and the links pointing there, or get rid of this one.
    """
    project = Campaign.query.filter_by(slug=slug).first_or_404()
    user = User.query.filter_by(id=user_id).first_or_404()
    project.enroll_user(user.id)
    return redirect(url_for('project_userlist', slug=slug))

@app.errorhandler(403)
def permission_denied(e):
    return render_template('errors/403_permission_denied.html'), 403

@app.errorhandler(413)
def request_too_large(e):
    return render_template('errors/413_request_entity_too_large.html'), 413

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404_not_found.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500_internal_server_error.html'), 500