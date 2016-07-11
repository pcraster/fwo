
#
# This is the WSGI configuration file. You need to define an
# application object which contains the webapp. To do this, the
# app is imported from the application directory as 'application'
# which is then served via WSGI. For testing purposes like 
# setting up mod_wsgi in apache it may be useful to have a test
# application which just says hello world. In that case comment
# out the "from application import app as application" line and
# define your own application below that.
#
import sys
sys.path.insert(0, '/var/www/fwo')
from application import app as application

#
#def application(environ, start_response):
#    status = '200 OK'
#    output = 'Hello World!'
#    response_headers = [('Content-type', 'text/plain'),
#                        ('Content-Length', str(len(output)))]
#    start_response(status, response_headers)
#    return [output]
#
