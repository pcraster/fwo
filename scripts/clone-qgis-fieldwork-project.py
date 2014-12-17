"""
This script clones an uploaded QGIS base map (project) and inserts
additional customized layers into the document. These layers are 
sourced from Spatialite/Sqlite databases in the user's data 
directory. In more detail, the following tasks are performed:

* 
"""

import sys
import os
import re
import hashlib
import argparse
import yaml
import subprocess

#import xml.etree.ElementTree as et
import lxml.etree as et

from PyQt4.QtCore import QFileInfo,QString,QStringList
from qgis.core import *
from pyspatialite import dbapi2 as db


def node_to_dict(node):
	QgsLayerTypes=['vector','raster','plugin'] 
	nodes=[]
	for child in node.children():
		if isinstance(child, QgsLayerTreeGroup):
			nodes.append({
				'node':'group',
				'visible':False if child.isVisible()==0 else True,
				'collapse':False,
				'name':str(child.name()),
				'children':node_to_dict(child)
			})
		elif isinstance(child, QgsLayerTreeLayer):
			lyr=child.layer()
			nodes.append({
				'node':'layer',
				'visible':False if child.isVisible()==0 else True,
				'collapse':False,
				'name':str(child.layerName()),
				'type':QgsLayerTypes[int(lyr.type())],
				'children':[]
			})
	return nodes

def tree_to_legend(node):
	QgsLayerTypes=['vector','raster','plugin']
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

def main():
	parser=argparse.ArgumentParser(description="Clone a fieldwork project")
	parser.add_argument("-c", "--clone", help="QGIS project file to clone")
	parser.add_argument("-t", "--target", help="QGIS project file to target")
	args = parser.parse_args()


	print "Map cloner..."


	QgsApplication([], True)
	QgsApplication.initQgis()

	proj=QgsProject.instance()
	
	try: 
		proj.read(QFileInfo(args.clone))
		print " * Loaded project: %s"%(proj.title())
	except Exception as e:
		print " * Failed to load project clone file %s"%(args.clone)
		sys.exit()

	# print proj.readEntry("SpatialRefSys","ProjectCRSProj4String")

	# print proj.readEntry("Gui","SelectionColorBluePart")

	# crs_list=map(str,proj.readListEntry("WMSCrsList","/")[0])
	# for crs in crs_list:
	# 	print "Found crs: %s"%(crs)

	# print proj.readEntry("Paths","Absolute")[0]

	
	#Overwrite various properties in the project which make it easier/neater to serve via WMS:

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

	#print node_to_dict(root)
	root=proj.layerTreeRoot()

	#Find the "Spreadsheets" group, or create it if we couldn't find it.
	spreadsheets=root.findGroup("Spreadsheets")
	if not spreadsheets:
		spreadsheets=root.insertGroup(0,QString("Spreadsheets"))

	#Lets add a vector points layer from a spatialite database
	sqlite_db="/var/fieldwork-data/campaigns/fieldwork-online-demo-project/userdata/3-student/features.sqlite"
	sqlite_schema=""
	sqlite_table="fwo_alldataseptember2013"
	sqlite_geom_col="geom"

	conn=db.connect(sqlite_db)
	cur=conn.cursor()
	


	fwo_metadata=cur.execute("SELECT name,title FROM fwo_metadata")
	table_list=[]
	for (sqlite_table,title) in fwo_metadata:
		table_list.append([sqlite_table,title])
	conn.close()
	#table_list=map(str,table_list)
	print table_list




	mapreg=QgsMapLayerRegistry.instance()

	for (sqlite_table,title) in table_list:
		# c=cur.execute("SELECT COUNT(*) FROM %s"%(sqlite_table))
		# for t in c:
		# 	table_rows=t[0]

		# print "Found %i rows in table %s (%s)"%(table_rows,sqlite_table,title)
		#print "%s -> %s"%(sqlite_table,title)

		uri=QgsDataSourceURI()
		uri.setDatabase(sqlite_db)
		uri.setDataSource(sqlite_schema, sqlite_table, sqlite_geom_col)

		print " * DB URI:"+uri.uri()
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

	#

	#print "Feature listing:"
	#for feature in vectorlayer.getFeatures():
#		print "Found a feature!"



	#root.addLayer(vectorlayer)
	#print spreadsheets

	#For each layer in the Spreadsheets group, if the name matches a table name in the user's spatialite database, then sneakily replace the datasource
	# for layer in spreadsheets:
	# 	print "Name: %s"%(layer.layerName())
	# 	print "Id: %s"%(layer.layerId())
		
	#print map(str,spreadsheets.findLayers())



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
	proj.write(QFileInfo(args.target))

	xml='<legend updateDrawingOrder="true">\n'+tree_to_legend(root)+'</legend>'
	
	canvas=et.fromstring(xml)


	target=et.parse(args.target)

	#print et.tostring(target, pretty_print=True)

	rt=target.find(".").append(canvas)
	target.write(args.target)

	QgsApplication.exitQgis()

	#
	#invent_some_xml_nodes(file)
	#

	#
	#
	#
	#print "Input/output diff:"
	#subprocess.call("diff %s %s"%(args.clone,args.target),shell=True)
    
if __name__ == "__main__":
    main()