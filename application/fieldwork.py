from flask import Flask, render_template, request, redirect, url_for
from flask.ext.mail import Mail
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.user import current_user, login_required, roles_required, UserManager, UserMixin, SQLAlchemyAdapter
from slugify import slugify

app = Flask(__name__)
app.config.from_object("settings")

# Load local_settings.py if file exists
try: 
	app.config.from_object('local_settings')
except: 
	pass

# Initialize Flask extensions
db = SQLAlchemy(app)
mail = Mail(app)

# Define User model. Make sure to add flask.ext.user UserMixin!!
class User(db.Model, UserMixin):
	id = db.Column(db.Integer, primary_key=True)
	active = db.Column(db.Boolean(), nullable=False, default=False)
	username = db.Column(db.String(50), nullable=False, unique=True)
	fullname = db.Column(db.String(50), nullable=False, unique=False)
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

	@property
	def working_on(self):
		"""
		Return the project the user is currently working on.
		"""
		pass
	@property
	def slug(self):
		return slugify("%i-%s"%(self.id,self.username))


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
	users = db.relationship('User', secondary='campaign_users', backref=db.backref('campaigns',lazy='dynamic'))
	def __init__(self,name,description):
		self.name=name
		self.description=description
		self.slug=slugify(name)
	def __repr__(self):
		return "<Campaign: /campaigns/%s>"%(self.slug)

class CampaignUsers(db.Model):
	id = db.Column(db.Integer(), primary_key=True)
	campaign_id = db.Column(db.Integer(), db.ForeignKey('campaign.id', ondelete='CASCADE'))
	user_id = db.Column(db.Integer(), db.ForeignKey('user.id', ondelete='CASCADE'))

# Create all database tables
db.create_all()

# Setup Flask-User
db_adapter = SQLAlchemyAdapter(db,  User)       # Select database adapter
user_manager = UserManager(db_adapter, app)     # Init Flask-User and bind to app

if Role.query.count()==0:
	db.session.add(Role(name='administrator'))
	db.session.add(Role(name='supervisor'))
	db.session.add(Role(name='student'))
	db.session.commit()

# Set up some demo users
if not User.query.filter(User.username=='admin').first():
    admin = User(username='admin', fullname='Site Admin', email='kokoalberti@yahoo.com', active=True, password=user_manager.hash_password('admin'))
    admin.roles.append(Role.query.filter(Role.name=='administrator').first())
    admin.roles.append(Role.query.filter(Role.name=='supervisor').first())
    db.session.add(admin)
    db.session.commit()
if not User.query.filter(User.username=='supervisor').first():
    supervisor = User(username='supervisor', fullname='Site Supervisor', email='k.alberti@uu.nl', active=True, password=user_manager.hash_password('supervisor'))
    supervisor.roles.append(Role.query.filter(Role.name=='supervisor').first())
    db.session.add(supervisor)
    db.session.commit()
if not User.query.filter(User.username=='student').first():
    student = User(username='student', fullname='Sam Student', email='k.alberti@students.uu.nl', active=True, password=user_manager.hash_password('student'))
    student.roles.append(Role.query.filter(Role.name=='student').first())
    db.session.add(student)
    db.session.commit()

if not Campaign.query.filter(Campaign.name=='Fieldwork Demo').first():
	campaign = Campaign(name="Fieldwork Demo",description="A fieldwork campaign for demonstration purposes")
	campaign.users.append(User.query.filter(User.username=='student').first())
	campaign.users.append(User.query.filter(User.username=='supervisor').first())
	campaign.users.append(User.query.filter(User.username=='admin').first())
	db.session.add(campaign)
	db.session.commit()


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



@app.route("/admin")
@login_required
@roles_required("administrator")
def admin():
	return render_template("admin.html",
		users=User.query.all(),
		campaigns=Campaign.query.all()
	)

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

@app.route("/projects/")
@login_required
def project_list():
	project_list=None
	if current_user.is_admin:
		project_list=Campaign.query.all()
	else:
		project_list=Campaign.query.filter(Campaign.users.any(id=current_user.id)).all()
	return render_template("project-list.html",project_list=project_list)


@app.route("/projects/<slug>/")
@login_required
def project_userlist(slug=None):
	"""
	Lists the users which are participating in this project.
	"""
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	users=User.query.filter(User.campaigns.contains(project)).all()
	return render_template("project-userlist.html",project=project,users=users)


@app.route("/projects/<slug>/<user_id>/")
@login_required
def project_page(slug=None,user_id=None):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first()
	return render_template("project.html",project=project,user=user)


@app.route("/projects/<slug>/<user_id>/data",methods=["GET","POST"])
@login_required
def upload(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	if request.method=="POST":
		return render_template("upload.html",project=project,user=user)
	else:
		return render_template("upload.html",project=project,user=user)

@app.route("/projects/<slug>/<user_id>/maps")
@login_required
def project_maps(slug,user_id):
	project=Campaign.query.filter_by(slug=slug).first_or_404()
	user=User.query.filter_by(id=user_id).first_or_404()
	return render_template("maps.html",project=project,user=user)

if __name__ == "__main__":
    app.run(debug=True)


