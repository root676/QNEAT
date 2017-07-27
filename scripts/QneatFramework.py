from PyQt4.QtCore import QVariant

from qgis.core import *
from qgis.analysis import *
from qgis.networkanalysis import *


import gdal, ogr


class QneatBaseCalculator():
	
	def __init__(self, input_network, input_points, input_directionFieldId, input_directDirectionValue, input_reverseDirectionValue, input_bothDirectionValue, input_defaultDirection):
		#init datasets
		self.input_network = input_network
		self.input_points = input_points
		#init direction fields
		self.directionFieldId = input_directDirectionValue
		self.input_directDirectionValue = input_directDirectionValue
		self.input_reverseDirectionValue = input_reverseDirectionValue
		self.input_bothDirectionValue = input_bothDirectionValue
		self.input_defaultDirection = input_defaultDirection
		#init computabiliyt and crs
		self.ComputabilityStatus = self.checkComputabilityStatus(input_network, input_points)
		self.AnalysisCrs
		#init graph analysis
		self.points = self.setupAnalysisPoints()
		self.network = self.setupNetworkAnalysis()
		
		
		
	def setupAnalysisPoints(self):
		self.log("Getting all analysis points")
		analysis_point_request = QgsFeatureRequest().setFilterFids(self.input_points.allFeatureIds())
		self.points = self.input_points.getFeatures(analysis_point_request)
	
	def setupNetworkanalysis(self):
		#direction can be added
		self.log("Setting up Network Analysis")
		#line director args: layer, directionFieldId, str directDirectionValue, str reverseDirectionValue, str bothDirectionValue, int defaultDirection 
		# EXAMPLE: QgsLineVectorLayerDirector(self.input_network, -1, '', '', '', 3)
		self.log("Adding direction information")
		director = QgsLineVectorLayerDirector(self.input_network, self.directionFieldId, self.input_directDirectionValue, self.input_reverseDirectionValue, self.input_bothDirectionValue, self.input_defaultDirection)
		#Use distance as cost-strategy pattern.
		self.log("Setting distance as cost property")
		properter = QgsDistanceArcProperter()
		#add the properter to the QgsGraphDirector
		director.addProperter(properter)
		self.log("Setting the graph builders spatial reference")
		builder = QgsGraphBuilder(self.AnalysisCrs)
		#tell the graph-director to make the graph using the builder object and tie the start point geometry to the graph
		self.log("Tying input_points to the graph")
		tiedPoints = director.makeGraph(builder, [feature.geometry().asPoint() for feature in self.points])
		#get the graph
		self.log("Build the graph")
		self.network = builder.graph()
		
	
	def checkComputabilityStatus(self):
		input_network_srid = self.input_network.crs().authid()
		input_points_srid = self.input_points.crs().authid()
		if input_network_srid == input_points_srid:
			self.log("Input datasets match in spatial reference:")
			self.log("NetworkCRS == PointCRS: %d == %d".format(input_network_srid, input_points_srid))
			self.AssignAnalysisCrs() #if srids match, assign network crs to object as AnalysisCrs
			return True 	
		else:
			self.log("Input datasets do not have the same spatial reference:")
			self.log("Network-dataset: %d".format(input_network_srid))
			self.log("Point-dataset: %d".format(input_points_srid))
			self.log("Please reproject input datasets so that they share the same spatial reference!")
			return False
	
	
	def AssignAnalysisCrs(self):
		self.log("Setting analysis CRS")
		self.AnalysisCrs = self.input_network.crs()
	
	
	def log(self, message):
		QgsMessageLog.LogMessage(message)
	
	
	def populateMemoryQgsVectorLayer(self, string_geomtype, string_layername, list_geometry, list_qgsfield):
		
		#create new vector layer from self.crs
		vector_layer = QgsVectorLayer(string_geomtype, string_layername, "memory")
		
		#set crs from class
		vector_layer.setCrs(self.crs)
		
		#set fields
		provider = vector_layer.dataProvider()
		provider.addAttributes(list_qgsfield) #[QgsField('fid',QVariant.Int),QgsField("origin_point_id", QVariant.Double),QgsField("iso", QVariant.Int)]
		vector_layer.updateFields()
		
		#fill layer with geom and attrs
		vector_layer.startEditing()
		for i, geometry in enumerate(list_geometry):
			feat = QgsFeature()
			feat.setGeometry(geometry)#geometry from point
			feat.setAttributes(list_qgsfield[i])
			vector_layer.addFeature(feat, True)
		vector_layer.commitChanges()
		
		return vector_layer
	
	
	
class QneatIsochroneCalculator(QneatBaseCalculator):
	
	def __init__(self, input_network, input_points, input_directionFieldId, input_directDirectionValue, input_reverseDirectionValue, input_bothDirectionValue, input_defaultDirection, iso_steps, output_interpolation_path, output_polygon_path):
		QneatBaseCalculator.__init__(self, input_network, input_points, input_directionFieldId, input_directDirectionValue, input_reverseDirectionValue, input_bothDirectionValue, input_defaultDirection)
		self.iso_steps = iso_steps
		self.output_interpolation = output_interpolation_path
		self.output_polygons = output_polygon_path
	
	
	def calcIsoPoints(self):
		self.iso_points = 1
		return self.iso_points	
		
		
	def interpolateIsoPoints(self):	
		return 0
	
	
	def polygonize(self):
		return 0
	

class QneatODMatrixCalculator(QneatBaseCalculator):
	
	def __init__(self, input_network, input_points, output_matrix):
		QneatBaseCalculator.__init__(self, input_network, input_points)
		self.output_matrix = output_matrix
	
	def CalcMatrix(self):
		self.iso_points = 1
		return self.iso_points	
		
	

if __name__ == '__main__':
	IsoCalcObj = QneatIsochroneCalculator("graph", "points", "50/100/150/200", "interpolation_raster", "polygons")
	IsoCalcObj.CalcIsoPoints()
	#IsoCalcObj.getCrs("4325")
	print IsoCalcObj.iso_points
	print IsoCalcObj.crs
	print dir(IsoCalcObj)
