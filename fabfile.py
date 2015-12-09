import os

from fabric.api import *

env.hosts=['geowebfg01.geo.uu.nl']


env.user=prompt('Please enter a remote user:')

env.code_dir='/var/www/fieldwork_online'
env.data_dir = '/var/wwwdata/fieldwork_online'
env.as_user = 'apache'



def deploy():
	#
	# Pulls the latest copy from the git repository
	#
    with settings(warn_only=True):
        if sudo("test -d %s"%(os.path.join(env.code_dir,".git"))).failed:
            sudo("git clone git://git.code.sf.net/p/pcraster/fieldwork_online %s"%(env.code_dir))
            sudo("chown -R apache:apache %s"%(env.code_dir))
        if sudo("test -d %s"%(env.data_dir)).failed:
            sudo("mkdir %s"%(env.data_dir))
            sudo("chown -R apache:apache %s"%(env.data_dir))
    with cd(env.code_dir):
        sudo("git pull",user=env.as_user)
        #put("./application/local_settings.py","application/local_settings.py",use_sudo=True)
        sudo("touch fieldwork_online.wsgi",user=env.as_user)


def manage_createdb():
	with cd(env.code_dir):
		sudo("python manage.py createdb",user=env.as_user)

def manage_dropdb():
    with cd(env.code_dir):
        sudo("python manage.py dropdb",user=env.as_user)

def manage_reset_password():
    username=prompt('Please enter a username to reset:')
    with cd(env.code_dir):
        sudo("python manage.py reset_password %s"%(username),user=env.as_user)

def install_requirements():
	with cd(env.code_dir):
		sudo("pip install -r ./application/requirements.txt")

