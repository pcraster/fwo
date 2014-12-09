import sys
import os
import re
import hashlib
import argparse
import yaml
import subprocess



from PyQt4.QtCore import QFileInfo,QString,QStringList
from qgis.core import *
from pyspatialite import dbapi2 as db

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

	#Set the allowed CRS for the WMS service, otherwise the WMS responses get bloated with useless crud
	#proj.writeEntry("WMSCrsList","/",QStringList(map(QString,["EPSG:4326","EPSG:3857"])))

	#Set the project to use absolute paths
	#proj.writeEntry("Paths","Absolute",QString("true"))
	#canvas = QgsMapCanvas()
	#canvas.show()


	tree=proj.layerTreeRegistryBridge()

	#print dir(tree)

	#proj.write(QFileInfo(args.target))
	#QgsApplication.exitQgis()
	#sys.exit()

	#print node_to_dict(root)
	root=proj.layerTreeRoot()

	#Find the "Spreadsheets" group, or create it if we couldn't find it.
	spreadsheets=root.findGroup("Spreadsheets")
	if not spreadsheets:
		spreadsheets=root.insertGroup(0,QString("Spreadsheets"))

	#Lets add a vector points layer from a spatialite database
	sqlite_db="/var/fieldwork-data/campaigns/fieldwork-demo/userdata/u_3/features.sqlite"
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

	#print root.findLayerIds()

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




	proj.write(QFileInfo(args.target))

	QgsApplication.exitQgis()

	#
	#
	#
	print "Input/output diff:"
	subprocess.call("diff %s %s"%(args.clone,args.target),shell=True)
    
if __name__ == "__main__":
    main()