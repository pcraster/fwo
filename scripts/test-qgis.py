try:
	import sys
	import os
	import re
	import hashlib
	import argparse
	import subprocess
	import random
	import lxml.etree as et
	sys.path.append('/usr/local/share/qgis/python')
	from PyQt4.QtCore import QFileInfo,QString,QStringList
	from qgis.core import *
	from pyspatialite import dbapi2 as db
except Exception as e:
	print " * Failed trying to import python module! Hint:%s"%(e)
	sys.exit(1)

def main():
	print "Lets go"
	parser=argparse.ArgumentParser(description="Test a fieldwork project")
	parser.add_argument("-c", "--clone", help="QGIS project file to clone")
	args = parser.parse_args()

	QgsApplication([], False) #initialize the qgis application
	
	#QgsApplication.setPrefixPath("", True)
	QgsApplication.initQgis()

	print "Settings"
	print QgsApplication.showSettings()
	print "Provider list"
	plist=QgsProviderRegistry.instance().providerList()
	for p in plist:
		print " * %s"%(str(p))

	proj=QgsProject.instance()
	try: 
		proj.read(QFileInfo(args.clone))
	except Exception as e:
		print " * Failed to load project clone file %s"%(args.clone)
		sys.exit(3)

	root = QgsProject.instance().layerTreeRoot()
	layer1 = QgsVectorLayer("Point", "Layer 1", "memory")
	QgsMapLayerRegistry.instance().addMapLayer(layer1)
	#node_layer1 = root.addLayer(layer1)

	proj.write(QFileInfo("/tmp/output.qgs"))


if __name__ == "__main__":
    main()
