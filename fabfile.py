import os

from fabric.api import *

env.hosts=['geowebfg01.geo.uu.nl']
env.user=prompt('Please enter a remote user:')

def prepare_deploy():
	local("./manage.py test")

def deploy():
	#
	# Pulls the latest copy from the git repository
	#
    code_dir = '/var/www/fieldwork_online'
    data_dir = '/var/wwwdata/fieldwork_online'
    as_user='apache'
    with settings(warn_only=True):
        if sudo("test -d %s"%(os.path.join(code_dir,".git"))).failed:
            sudo("git clone git://git.code.sf.net/p/pcraster/fieldwork_online %s"%(code_dir))
            sudo("chown -R apache:apache %s"%(code_dir))
        if sudo("test -d %s"%(data_dir)).failed:
            sudo("mkdir %s"%(data_dir))
            sudo("chown -R apache:apache %s"%(data_dir))
    with cd(code_dir):
        sudo("git pull",user=as_user)
        sudo("touch fieldwork_online.wsgi",user=as_user)

def manage_createdb():
	with cd(code_dir):
		sudo("python manage.py createdb",user=as_user)

