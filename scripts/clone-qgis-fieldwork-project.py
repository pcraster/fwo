"""
Map update script for Fieldwork Online web app.
===============================================

This script clones a basemap present on the system (specified in the --clone argument) into a user directory (specified in the --target argument). It does so using the QGIS api and some additional Python code. In the meantime it also checks for user uploaded data in a sqlite database in the user directory. If that exists then the data is inserted into the QGIS project as extra layers. The script exits with a return code with the following meaning:

	0:	Everything went ok!
	1: 	Occurs when an error causes the script to exit which is not caught by a try/catch. This shouldnt happen really...
	2: 	A lockfile exists for the output project. Another instance of this script is still writiing to it??
	3: 	Could not open the QGIS project file (*.qgs) with the QGIS python api
	4:	Another exception occurred while running the script. Try to run it manually to see what went wrong.
	5:  Failed while trying to import required python modules.

It is also possible to call this script with the --test argument. This does not actually do anything except test whether the script can actually run and do its imports properly.
"""


try:
	import sys
	import os
	import re
	import hashlib
	import argparse
	import yaml
	import subprocess
	import random
	import lxml.etree as et

	from PyQt4.QtCore import QFileInfo,QString,QStringList
	from qgis.core import *
	from pyspatialite import dbapi2 as db
except Exception as e:
	print " * Failed trying to import python module! Hint:%s"%(e)
	sys.exit(1)


def tree_to_legend(node):
	"""
	Returns an xml string of the <legend> node of a qgis project, with <legendgroup> subnodes to define groups and <legendlayers> with <filegroup>s to define the actual data layers. These xml nodes must be present in the qgis project file in order for qgis server return a proper response to a GetProjectSettings WMS request.
	"""
	xml=''
	for child in node.children():
		if isinstance(child, QgsLayerTreeGroup):
			xml+='<legendgroup open="true" checked="Qt::Checked" name="'+str(child.name())+'">\n'
			xml+=tree_to_legend(child)
			xml+='</legendgroup>\n'
		elif isinstance(child, QgsLayerTreeLayer):
			xml+='<legendlayer drawingOrder="-1" open="false" checked="Qt::Checked" name="'+str(child.layerName())+'" showFeatureCount="0">\n'
			xml+='    <filegroup open="false" hidden="false">\n'
			xml+='        <legendlayerfile isInOverview="0" layerid="'+str(child.layerId())+'" visible="1"/>\n'
			xml+='    </filegroup>\n'
			xml+='</legendlayer>\n'
	return xml

def sanitize_layer_names(layernames):
	"""
	Returns a sanitized list of layer names. Qgis layer ids contain a timestamp of when the layer was created. This results in ugly layer names (as well as odd WMS/WFS layer names) like "TopografischeKaart20141204153632502" which is confusing for humans using the WMS/WFS services. Also, when a project is updated with new data this timestamp can change if the layer is inserted again while the project is being cloned. This function sanitizes the layer names by making new unique layer id's from the sensible layer name (like "Topografishe Kaart"). The following steps are taken:
	* Remove all non-alphanumeric and _ characters
	* Remove all whitespace blocks
	* If the name is not unique, append "_<n>" to the name until it is unique, where <n> is an incrementing integer. 
	"""
	layer_ids=[]
	for layer_id,layer_name in layernames:
		old_layer_id=layer_id
		layer_id=re.sub(r'\W+',' ',layer_name).lower()
		layer_id="_".join(map(str,layer_id.split()))
		proposed_id=layer_id
		loop=1
		while proposed_id in layer_ids:
			proposed_id="%s_%i"%(layer_id,loop)
			loop+=1
		layer_ids.append(proposed_id)
		layer_id=proposed_id
		yield (old_layer_id,layer_id)

def safe_layer_names():
	layers=QgsMapLayerRegistry.instance().mapLayers()
	for name,layer in layers.iteritems():
		prettyname=layer.name()
		newname=re.sub(r'\W+',' ',str(layer.name())).lower()
		newname="_".join(map(str,newname.split()))
		layer.setLayerName(QString(newname))
		layer.setTitle(QString(prettyname))
		layer.reload()
		print "%s->%s"%(name,newname)
	return False

def get_layer_by_name(layer_name):
	"""
	Returns the first layer matching name layer_name
	"""
	layers=QgsMapLayerRegistry.instance().mapLayers()
	for name,layer in layers.iteritems():
		if layer.name()==layer_name:
			return layer
	return False

def get_layer_by_title(layer_title):
	"""
	Returns the first layer matching title layer_title
	"""
	layers=QgsMapLayerRegistry.instance().mapLayers()
	for name,layer in layers.iteritems():
		if layer.title()==layer_title:
			return layer
	return False

def main():
	"""
	This script clones an uploaded QGIS base map (project) and inserts additional customized layers into the document. These layers are sourced from Spatialite/Sqlite databases in the user's data directory, mostly sources from spreadsheets that the user has uploaded themselves. Since this script may be executed under a variety of circumstances a lock file is also created for the output project file. The webapp checks for this lockfile when displaying maps and creating new data and returns an error if it exists, as that means that this script is still working on the project file. 

	It completes the following actions:
		- Make a lock file for the output file
		- Open the clone project file using the qgis python api
		- Overwrite various properties of the qgis project file to ensure that it can be served via qgis-server as a WMS/WFS service. These modifications are:
			* Set the WMSServiceCapabilities checkbox in the project properties to true
			* Limit the CRSes available, this is a big performance win (see: http://sourcepole.ch/qgis-cloud-speed-up-the-loading-time-of-the-web-client)
			* Use layer id's instead of names to identify wms layers by. Layer names can contain spaces and other characters which can cause things to fail on the WMS end.
			* Make the project use absolute paths
		- Checks the fwo_metadata table in the features.sqlite file in the userdata directory. In the fwo_metadata table, the feature tables belonging to this user are listed. For each of these tables, the script checks if a layer exists in the qgis project. If so, it updates the datasource of that layer to point to that sqlite layer instead, thereby allowing qgis-server to server the users' uploaded features from within the template project for the fieldwork campaign. If not, we still want to be able to display the data, but with a default styling. In that case the layer is added to a "Spreadsheets" group in the qgis project. Any layes which are not predefined in the template end up here.
		- After updating the qgis project, the file is saved to the user's map directory. 
		- When the file is saved it is missing the <canvas> node. This node is created using recursive calls to  tree_to_legend() and the lxml Python module. The canvas node is inserted in the new qgis project file, which is then overwritten.
		- The lock file for the output file is removed.

	To do:
		- Updating the layers to use a unique id adds a timestamp which changes every time we (re)add layers, this means WMS layer names will also change. Best solution is not to use unique id's, but sanitize the layer names to only have alphanumeric and _ characters. But how to do this?

	Notes:
		- This script needs to be reasonably bulletproof as it can be called upon in various scenarios like uploading a new basemap, adding files to a basemap, enrolling students in a fieldwork, etc.
	"""
	parser=argparse.ArgumentParser(description="Clone/update a fieldwork project")
	parser.add_argument("-c", "--clone", help="QGIS project file to clone")
	parser.add_argument("-t", "--target", help="User directory of the Fieldwork Online application to target")
	#parser.add_argument("--test", help="Test the script")
	args = parser.parse_args()

	randomstring=''.join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(6))
	targfile=os.path.join(args.target,"map","project-%s.qgs"%(randomstring))

	lockfile=targfile+".lock"
	if os.path.isfile(lockfile):
		print " * Lockfile exists for target project. Perhaps another call was made to this script which has not finished yet?"
		sys.exit(2)
	else:
		try:
			open(lockfile,'a').close() #create a lockfile

			QgsApplication([], True) #initialize the qgis application
			QgsApplication.initQgis()

			proj=QgsProject.instance()
			try: 
				proj.read(QFileInfo(args.clone))
			except Exception as e:
				print " * Failed to load project clone file %s"%(args.clone)
				sys.exit(3)

			#
			#Overwrite various properties in the project which make it easier/neater to serve via WMS
			#
			#Set the OWS service capabilities so qgis server will actually serve this project
			proj.writeEntry("WMSServiceCapabilities","/",QString("true"))
			#Set the WMS title and other data
			proj.writeEntry("WMSServiceTitle","/",QString("Fieldwork Online WMS Service"))
			proj.writeEntry("WMSContactMail","/",QString("k.alberti@uu.nl"))
			#Set the allowed CRS for the WMS service, otherwise the WMS responses get bloated with useless crud
			proj.writeEntry("WMSCrsList","/",QStringList(map(QString,["EPSG:4326","EPSG:3857"])))
			#Set the project WMS to use layer id's instead of layer names
			proj.writeEntry("WMSUseLayerIDs","/",QString("true"))
			#Set the project to use absolute paths
			proj.writeEntry("Paths","Absolute",QString("true"))

			tree=proj.layerTreeRegistryBridge()
			root=proj.layerTreeRoot()


			#Lets add the user uploaded features which are in a features.sqlite file
			sqlite_db=os.path.join(args.target,"map","features.sqlite")

			datasource_updates=[]

			#Update all the layer names so they are 'safe' with no spaces, weird 
			#characters, or timestamps in their ID's (qgis does this by itself..)
			#safe_layer_names()


			mapreg=QgsMapLayerRegistry.instance()
			if not os.path.isfile(sqlite_db):
				# There is no sqlite file with user-uploaded features. Therefore we can just
				# copy the base project as is.
				print " * Sqlite file ./map/features.sqlite not found in directory %s. Just use the base project as is and skip inserting/replacing the layers with user uploaded features."%(args.target)
			else:


				#Connect the spatialite database with the user's features and extract
				#a list of tables/layers.
				try:
					conn=db.connect(sqlite_db)
					cur=conn.cursor()
					fwo_metadata=cur.execute("SELECT name,title FROM fwo_metadata")
					table_list=[]
					for (sqlite_table,title) in fwo_metadata:
						table_list.append([sqlite_table,title])
					conn.close()
					print table_list

					#Find the "Spreadsheets" group, or create it if we couldn't find it.
					spreadsheets=root.findGroup("Spreadsheets")
					if not spreadsheets:
						spreadsheets=root.insertGroup(0,QString("Spreadsheets"))

					
					new_layers=[]
					for (sqlite_table,title) in table_list:
						#
						# Loop through the user uploaded tables and check if one with
						# an identical name exists in the qgis project. If so, switch
						# the data sources and point it to the table which contains the
						# user data. If it does not exist, create a new vector layer and
						# add it to the "Spreadsheets" group.
						#
						#
						uri=QgsDataSourceURI()
						uri.setDatabase(sqlite_db)
						uri.setDataSource("", sqlite_table, "geom")
						print " * DB URI (new):"+uri.uri()


						existing_layer=get_layer_by_title(title)
						if existing_layer != False:
							#So the layer exists already! Good news, that means it probably
							#has some custom styling that we would like to preserve. All we 
							#need to do is switch the datasource to point to the spatialite
							#file in the user's directory which contains his uploaded features.
							#Unfortunately this does not work in the QGIS api!! For more info
							#on that see http://gis.stackexchange.com/questions/6157/in-qgis-is-it-possible-to-edit-the-datasource-of-a-postgis-layer

							#Instead what we do is make a list of datasources to update in 
							#the form of datasource_updates[<layername>]='<newdatasourceuri>'
							#Then at the end of the script when we edit the xml file, use xpath
							#to loop through the <maplayer> elements, and for each <maplayer> 
							#with a subnode <layername>, replace the datasource uri with the
							#correct one.
							layername=str(existing_layer.name())
							datasource=str(uri.uri())
							datasource_updates.append((layername,datasource))
						else:
							#So this layer does not exist yet! Because we have no idea what
							#sort of styling to apply, or where to insert the layer, the 
							#default behavior applies. That means make a new vector layer with
							#the spatialite database as a datasource, and insert it into the
							#"Spreadsheets" group of the qgis project. It will then receive
							#default styling applied by qgis.
							print "Layer %s does not exist!"%(title)
							try:
								vectorlayer=QgsVectorLayer(uri.uri(),title,"spatialite")
								if vectorlayer.isValid():
									print " * Vector layer is valid!"
							except Exception as e:
								print " * Failed to create layer!"
							
							print " * Creating the layer went ok!"
							mapreg.addMapLayer(vectorlayer,False)
							print " * Try to add it to the group!"
							spreadsheets.addLayer(vectorlayer)
							print " * Success! Layer is called: %s\n\n"%(title)
						#end adding user defined features
				except Exception as e:
					print " * No userdata found!"

			id_replacements=[]
			wfs_layers=[] #used to store a list of layer names for which to enable WFS
			layers=mapreg.mapLayers()
			for name,layer in layers.iteritems():
				prettyname=layer.name()
				newname=re.sub(r'\W+',' ',str(layer.name())).lower()
				newname="_".join(map(str,newname.split()))
				layer.setLayerName(QString(newname))
				layer.setTitle(QString(prettyname))
				layer.reload()
				layer_id=str(layer.id())
				id_replacements.append((layer_id,newname))
				print "%s->%s (id=%s; type=%s)"%(name,newname,layer_id,layer.type())
				if layer.type()==0:
					wfs_layers.append(layer_id)


			#print "Vector layers:"
			#print ",".join(wfs_layers)
			proj.writeEntry("WFSLayers","/",QStringList(map(QString,wfs_layers)))
			#
			#Now lets save the user's copy of the project in the userdata directory
			#so that the user's map page can show the custom map. Unfortunately...
			#
			#When using QgsProject.write() from a standalone script, several nodes 
			#in the output file go missing, such as <mapcanvas>,<legend> and a few others. 
			#Unfortunately this is because these nodes are written by components
			#which are part of the QGIS Desktop. When a project write is done,
			#a signal is sent which - in QGIS App/GUI - is picked up on, but in
			#a standalone script these signals are ignored, resulting in the 
			#several missing nodes. For more info see:
			#
			#http://lists.osgeo.org/pipermail/qgis-developer/2014-December/035860.html
			#http://lists.osgeo.org/pipermail/qgis-developer/2014-December/035928.html
			#
			#It doesn't seem like much can be done about this at the current time. Without
			#these nodes in the XML file however, qgis server can't properly server the
			#files as WMS/WFS services. As a workaround, we can use the data from the 
			#root node to construct our own <legend> xml element which we insert into
			#the xml file afterwards. This is an ugly workaround but at the moment it
			#is really the only way of serving a project via qgis server that has been
			#modified with a standalone script which uses the qgis api.
			proj.write(QFileInfo(targfile))


			#Turn the target qgis project file info an ET object
			target=et.parse(targfile)

			#Update the data sources!
			for (layername,datasource) in datasource_updates:
				maplayers=target.xpath("//maplayer[layername='"+layername+"']")
				for maplayer in maplayers:
					maplayer.find("datasource").text=datasource
				#print "%s -> %s"%(layername,datasource)



			#Create an XML string which defines the required legend node
			xml='<legend updateDrawingOrder="true">\n'+tree_to_legend(root)+'</legend>'
			#Turn it info an ET object
			legend=et.fromstring(xml)
			#Find the root node <qgis> and append the missing legend node to it.
			rt=target.find(".").append(legend)
			#Write the target file agaiin.
			target.write(targfile)

			#Update all the layer names that have a timestamp attached to it.
			#
			#Ok, gremlin #149... for some reason this nearly always works fine,
			#except in a few cases.. for example when the layer name/id is something
			#like Sheet1. Then, the layer just doesn't show up in qgis desktop or
			#via the wms service. WTF? Are layer names not allowed to be the same
			#as ids, is there a minimum length, why is this behavious so unpredicatable?
			#
			# data=""
			# with open(targfile) as f:
			# 	data=f.read()
			# 	for find,replace in id_replacements:
			# 		data=data.replace(find,replace)

			# with open(targfile,'w') as f:
			# 	f.write(data)



			#Exit qgis
			QgsApplication.exitQgis()
			sys.exit(0)
		except Exception as e:
			print " * An unexpected exception occurred: %s"%(e)
			sys.exit(4)
		finally:
			os.remove(lockfile) #Remove the lock file
    
if __name__ == "__main__":
    main()