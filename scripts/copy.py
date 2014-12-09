from PyQt4.QtCore import QFileInfo
from qgis.core import *

def main():
	QgsApplication([], True)
	QgsApplication.initQgis()

	proj=QgsProject.instance()
	proj.read(QFileInfo("source.qgs"))

	#do other stuff to the project

	proj.write(QFileInfo("target.qgs"))
	QgsApplication.exitQgis()
    
if __name__ == "__main__":
    main()