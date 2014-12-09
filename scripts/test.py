import os
import requests
import glob
import shutil
import json

from PyQt4.QtCore import QFileInfo
from qgis.core import *

QgsApplication([], True)
QgsApplication.initQgis()


#/var/fieldwork-data/campaigns/fieldwork-demo/basemaps/project.qgs --target=/var/fieldwork-data/campaigns/fieldwork-demo/userdata/u_3/test.qgs
_QgsLayerTypes=['vector','raster','plugin'] 
proj=QgsProject.instance()
proj.read(QFileInfo("/var/fieldwork-data/campaigns/fieldwork-demo/basemaps/project.qgs"))
def node_to_dict(node):
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
				'type':_QgsLayerTypes[int(lyr.type())],
				'children':[]
			})
	return nodes
print node_to_dict(proj.layerTreeRoot())