from application import app
from .models import * 


@app.route("/")
@login_required
def home():
    """
    The home view is not really a view but just redirects the visitor to the right place in
    more or less the following order:

    - Not logged in? Go to signup/login page. Done via @login_required decorator.
    - If the current user is not working on a project (current_user.current_project) then
      redirect to settings page so he can pick a project.
    - If you are working on a project, and you're not an admin or supervisor then go to the 
      project overview page (workspace) where you can select data, maps, etc.
    - If you are working on a project, and you're an admin or supervisor then do the project
      page where you can see all the enrolled users, and where you can check out their 
      workspaces.

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

@app.route("/admin",methods=["GET","POST"])
@login_required
@roles_required("administrator")
def admin():
    """
    Admin only view for administering the Fieldwork Online site. Admins can:

    - Create new projects
    - View existing projects and invite keys
    - View regsitered users and add/remove roles from them

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

@app.route("/settings",methods=["GET","POST"])
@login_required
def settings():
    """
    Settings page lets users:

    - View their own settings
    - Choose a fieldwork project (that they're enrolled in) to work on
    - Use an invite key to enroll themselves in a project.

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

@app.route("/projects/",methods=["GET","POST"])
@login_required
def project_list():
    flash("You can choose a project to work on from your settings page.","info")
    return redirect(url_for('settings'))

#
#
# View for the project page. This is an admin/supervisor only view and shows an overview
# of the project, lettings viewers look at another users workspace, upldate the basemap,
# or enroll other users manually.
#
#
@app.route("/projects/<slug>/",methods=["GET","POST"])
@login_required
def project(slug=None):
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
                if f.filename.endswith(".zip"):
                    try:
                        upload_file=os.path.join(project.projectdata,"map",f.filename)
                        f.save(upload_file)
                        #Don't use zipfile with context manager on py 2.6
                        #https://bugs.launchpad.net/horizon/+bug/955994
                        zf=zipfile.ZipFile(upload_file)
                        zip_filelist=zf.namelist()
                        zip_details="Extracted %s files: <code>"%(len(zip_filelist))+"</code> <code>".join(zip_filelist)+"</code>"
                        zf.extractall(os.path.join(project.projectdata,"map"))
                        flash("Zip file detected! %s"%zip_details,"ok")
                        project.basemap_version=db.func.now()
                        db.session.commit()
                        flash("File <code>%s</code> was uploaded to the project basemap. Timestamp: <code>%s</code>"%(f.filename,project.basemap_version),"ok")
                    except Exception as e:
                        flash("Zip file could not be extracted! Hint: %s"%(e),"error")
                if f.filename.endswith(".tif"):
                    try:
                        basemaps=os.path.join(project.projectdata,"backgroundlayers")
                        if not os.path.isdir(basemaps):
                            os.makedirs(basemaps)
                        upload_file=os.path.join(basemaps,f.filename)
                        f.save(upload_file)
                        #project.background_layers_update()
                        (head,tail)=os.path.split(upload_file)
                        name=tail.split(".")[0]

                        l=BackgroundLayer.query.filter_by(campaign_id=project.id,name=name).first()
                        if l==None:
                            #make new one
                            db.session.add(BackgroundLayer(
                                campaign_id=project.id,
                                name=name,
                                filename=upload_file
                            ))
                        else:
                            flash("Background layer with this name exists already... updating instead!")
                            #udpate it..
                            l.name=name
                            l.filename=upload_file

                        db.session.commit()
                        project.background_layers_update()
                        flash("Saved tiff file to project basemaps dir. make mapserver mapfile.","ok")
                    except Exception as e:
                        flash("Tif file could not be saved. Hint: %s"%(e),"error")

            elif request.form.get("action","")=="clearall":
                flash("Clearing all basemap data!","ok")
            elif request.form.get("action","")=="reload":
                project.basemap_update()
        if request.method=="GET":
            if request.args.get("action","")=="reload" and request.args.get("user_id","") != "":
                project.basemap_update(request.args.get("user_id",""))
            if request.args.get("action","")=="enroll" and request.args.get("user_id","") != "":
                project.enroll_user(request.args.get("user_id",""))

        #users=User.query.filter(User.campaigns.contains(project)).all()
        
        #role_student=Role.query.filter(Role.name=='student').first()
        role_supervisor=Role.query.filter(Role.name=='supervisor').first()
        role_admin=Role.query.filter(Role.name=='administrator').first()
        
        #print role_admin
        
        #students=User.query.filter(User.roles.contains(student)).all()
        #.filter(~User.roles.contains(role_supervisor))
        students=User.query.filter(User.campaigns.contains(project)).filter(~User.roles.contains(role_supervisor)).filter(~User.roles.contains(role_admin)).all()
        supervisors=User.query.filter(User.campaigns.contains(project)).filter(User.roles.contains(role_supervisor)|User.roles.contains(role_admin)).all()
        
        enrollable_users=User.query.filter(~User.campaigns.contains(project)).all()
        backgroundlayers=BackgroundLayer.query.filter_by(campaign_id=project.id).all()
        return render_template("project.html",project=project,supervisors=supervisors,students=students,enrollable_users=enrollable_users,backgroundlayers=backgroundlayers)
    else:
        #
        #Else forward the user to the user's fieldwork homepage
        #
        return redirect(url_for('project_overview',slug=project.slug,user_id=current_user.id))


#
#
# Main views for info in a user's workspace: Overview - Data - Maps - Feedback - Collaborate
#
#
@app.route("/projects/<slug>/<user_id>/")
@login_required
def project_overview(slug=None,user_id=None):
    project=Campaign.query.filter_by(slug=slug).first_or_404()
    user=User.query.filter_by(id=user_id).first_or_404()
    return render_template("project/overview.html",project=project,user=user)

@app.route("/projects/<slug>/<user_id>/data",methods=["GET"])
@login_required
def project_data(slug,user_id):
    project=Campaign.query.filter_by(slug=slug).first_or_404()
    user=User.query.filter_by(id=user_id).first_or_404()
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        abort(403)
    attachments=project.attachments(user_id)
    features=project.features(user_id)
    return render_template("project/data.html",project=project,user=user,attachments=attachments,features=features)

@app.route("/projects/<slug>/<user_id>/maps")
@login_required
def project_maps(slug,user_id):
    project=Campaign.query.filter_by(slug=slug).first_or_404()
    user=User.query.filter_by(id=user_id).first_or_404()
    
    cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first()
    if not project.basemap:
        flash("No basemap has been uploaded by the project administrator yet.","info")
        return render_template("project/empty.html",project=project,user=user)
    else:
        mapfile=project.basemap_for(user_id)
        return render_template("project/maps.html",project=project,user=user,wms_key=cu.wms_key,mapfile=mapfile,mapserver_url=app.config.get("MAPSERVER_URL"))


@app.route("/projects/<slug>/<user_id>/feedback",methods=["GET","POST"])
@login_required
def project_feedback(slug,user_id):
    project=Campaign.query.filter_by(slug=slug).first_or_404()
    user=User.query.filter_by(id=user_id).first_or_404()
    cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first()
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        return render_template("denied.html")
    if request.method=="POST":
        #Posting some feedback/comment or a reply to one
        if request.form.get('comment_parent','')=='':
            #A new comment
            try:
                db.session.add(Feedback(
                    user_id=user.id,
                    campaign_id=project.id,
                    comment_by=current_user.id,
                    comment_body=request.form.get('comment_body',''),
                    map_state=request.form.get('map_state',''),
                    map_view=request.form.get('map_view',''),
                    map_marker=request.form.get('map_marker','')
                ))
                db.session.commit()
                return jsonify(status="OK",message="Feedback posted!"),200
            except Exception as e:
                return jsonify(status="FAIL",message="Something went wrong trying to add feedback. Hint: %s"%(e)),500
        else:
            #A reply to an existing comment. This is stored as a FeedbackReply.
            parent=Feedback.query.get(int(request.form.get('comment_parent')))
            parent.replies.append(
                FeedbackReply(request.form.get('comment_body'),current_user.id)            
            )
            db.session.commit()
            
            
    feedback=Feedback.query.filter_by(user_id=user.id,campaign_id=project.id).order_by("comment_date desc").all()
    if not feedback:
        flash("No feedback has been left in this project yet.","info")
        return render_template("project/empty.html",project=project,user=user)
    else:
        return render_template("project/feedback.html",project=project,user=user,feedback=feedback,wms_key=cu.wms_key)

@app.route("/projects/<slug>/<user_id>/feedback.json",methods=["GET","POST"])
@login_required
def project_feedback_json(slug,user_id):
    project=Campaign.query.filter_by(slug=slug).first_or_404()
    user=User.query.filter_by(id=user_id).first_or_404()
    cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first()
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        return render_template("denied.html")
    feedback=Feedback.query.filter_by(user_id=user.id,campaign_id=project.id).order_by("comment_date desc").all()
    if not feedback:
        return jsonify([]),200
    else:
        f=[]
        for comment in feedback:
            replies=[]
            for reply in comment.replies:
                replies.append({
                    'reply_by':reply.comment_by_user.username,
                    'comment_age':reply.comment_age,
                    'comment_body':escape(reply.comment_body)
                })
            f.append({
                'id':comment.id,
                'comment_by':comment.comment_by_user.username,
                'comment_age':comment.comment_age,
                'comment_body':escape(comment.comment_body),
                'map_state':comment.map_state,
                'map_view':comment.map_view,
                'map_marker':comment.map_marker,
                'replies':replies
            })
            
        return json.dumps(f),200
        #return render_template("project/feedback.html",project=project,user=user,feedback=feedback,wms_key=cu.wms_key)

@app.route("/projects/<slug>/<user_id>/collaborate")
@login_required
def project_collaborate(slug,user_id):
    project=Campaign.query.filter_by(slug=slug).first_or_404()
    user=User.query.filter_by(id=user_id).first_or_404()
    if (user.id != current_user.id) and (not current_user.is_supervisor) and (not current_user.is_admin):
        return render_template("denied.html")

    cu=CampaignUsers.query.filter(CampaignUsers.campaign_id==project.id,CampaignUsers.user_id==user.id).first()
    return render_template("project/collaborate.html",project=project,user=user,cu=cu)

#
#
# Additional views for workspaces to take care of file uploads/viewing and enrollment
#
#
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
                    rc=excel_parser(upload_file,spatialite_file)

                if rc==False:
                    flash("An error occurred while trying to parse the uploaded Excel sheet. Please recheck your file and try again.","error")
                else:
                    project.basemap_update(user_id)
                    cu.update_lastactivity()
                    flash("Upload and processing of file <code>%s</code> completed."%(f.filename),"ok")
        except Exception as e:
            flash("An unexpected error occurred during the upload. Hint: %s"%(e),"error")
    return redirect(url_for('project_data',slug=slug,user_id=user_id))

@app.route("/projects/<slug>/<user_id>/enroll")
@login_required
@roles_required("administrator")
def project_enroll(slug=None,user_id=None):
    project=Campaign.query.filter_by(slug=slug).first_or_404()
    user=User.query.filter_by(id=user_id).first_or_404()
    project.enroll_user(user.id)
    return redirect(url_for('project_userlist',slug=slug))

#
#
# View for the WMS proxy
#
#
@app.route("/wms/<wms_key>")
def wmsproxy(wms_key=None):
    """
    This view acts as a HTTP proxy for the WMS server. There are a few reasons for going through the trouble of making a proxy:

    - Due to same origin policy the GetFeatureInfo requests need to originate on the same host. By having having a proxy this is guaranteed as the WMS response will always seem to come from the same server as the website, regardless of there the wms is actually located.
    - Sometimes QGIS server (if CRS restrictions have not been set manually in the project preferences) will return in XML a list of hundreds of allowed CRSes for each layer. This seriously bloats the GetProjectInfo request (it can become a 4MB+ file...). In this proxy we can manually limit the allowed CRSes to ensure the document does not become huge.
    - QGIS server does not support json responses! Since we are handling a lot of these WMS requests using JavaScript (also the GetFeatureInfo requests) it would be a lot easier, faster, and result in cleaner code, if the WMS server just returned JSON documents. Using this proxy we can add json support if the request argument FORMAT is set to "application/json", and do the conversion serverside with xmltodict. A JSONP callback argument is also supported.
    - We can camouflage the MAP parameter. This usually takes a full pathname to the map file. However, we dont want to reveal this to the world and let everybody mess about with it. Therefore we can override the MAP parameter in the proxy from the URL, that way the URL for a fieldwork WMS server will be /projects/fieldwork-demo/3/wms?<params> which is a lot neater than /cgi-bin/qgisserv.fcgi?MAP=/var/fieldwork-data/.....etc. There will be no MAP attribute visible to the outside in that case since it is added only on the proxied requests.
    - There are some opportunities for caching/compressing WMS requests at a later time if we use this method
    - We can limit access to the fieldwork data to only logged in users, or allow a per-project setting of who should be able to access the wms data. Qgis wms server does not really offer very useful http authentication methods, so this should provide a solution.

    Todo: return data in chunks rather than all in one go.
    """
    cu=CampaignUsers.query.filter(CampaignUsers.wms_key==wms_key).first_or_404()

    #project=Campaign.query.filter_by(slug=slug).first_or_404()
    project=Campaign.query.get(cu.campaign_id)
    user=User.query.get(cu.user_id)
    #user=User.query.filter_by(id=user_id).first_or_404()


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
        return Response("<pre>WMS server at %s returned status %i.</pre>"%(app.config["WMS_SERVER_URL"],r.status_code),mimetype="text/html"),r.status_code



@app.route("/install")
def install():
    """
    The install view is no longer used. After creating the database, the initial
    admin, supervisor, and student user, as well as the default dummy project, 
    are added by the "initdb" management command in ./manage.py. The users are 
    given random passwords which are saved in "install.txt" in the data directory
    for later reference.
    """
    return render_template("install.html")


#
#
# Some simple views for error handling.
#
#
@app.errorhandler(403)
def permission_denied(e):
    return render_template('errors/403_permission_denied.html'), 403

@app.errorhandler(413)
def request_too_large(e):
    return render_template('errors/413_request_entity_too_large.html'), 413

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404_not_found.html'), 404

# @app.errorhandler(500)
# def internal_server_error(e):
#     return render_template('errors/500_internal_server_error.html'), 500