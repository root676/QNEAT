

from qgis.core import *
from qgis.analysis import *
from qgis.networkanalysis import *

from PyQt4.QtCore import QVariant

from QneatUtilities import *


import gdal, ogr


class QneatBaseCalculator():
	
	
	"""
	QNEAT base-class:
	Provides basic logic for more advanced network analysis algorithms
	"""
	
	
	def __init__(self, input_network, input_points, input_directionFieldId, input_directDirectionValue, input_reverseDirectionValue, input_bothDirectionValue, input_defaultDirection):
		#init
		log("__init__: setting up parameters")
		#init datsets
		log("setting up datasets")
		self.input_network = input_network
		self.input_points = input_points
		
		#init direction fields
		log("setting up network analysis parameters")
		self.directionFieldId = input_directDirectionValue
		self.input_directDirectionValue = input_directDirectionValue
		self.input_reverseDirectionValue = input_reverseDirectionValue
		self.input_bothDirectionValue = input_bothDirectionValue
		self.input_defaultDirection = input_defaultDirection
	
		#init computabiliyt and crs
		log("__init__: checking computability and crs")
		self.ComputabilityStatus = self.checkComputabilityStatus(input_network, input_points)
		#init graph analysis
		#direction can be added
		log("__init__: setting up network analysis")
		log("getting all analysis points")
		self.list_input_points = self.input_points.getFeatures(QgsFeatureRequest().setFilterFids(self.input_points.allFeatureIds()))
		#line director args: layer, directionFieldId, str directDirectionValue, str reverseDirectionValue, str bothDirectionValue, int defaultDirection 
		# EXAMPLE: QgsLineVectorLayerDirector(self.input_network, -1, '', '', '', 3)
		log("Adding direction information")
		self.director = QgsLineVectorLayerDirector(self.input_network, self.directionFieldId, self.input_directDirectionValue, self.input_reverseDirectionValue, self.input_bothDirectionValue, self.input_defaultDirection)
		#Use distance as cost-strategy pattern.
		log("Setting distance as cost property")
		self.properter = QgsDistanceArcProperter()
		#add the properter to the QgsGraphDirector
		self.director.addProperter(self.properter)
		log("Setting the graph builders spatial reference")
		self.builder = QgsGraphBuilder(self.AnalysisCrs)
		#tell the graph-director to make the graph using the builder object and tie the start point geometry to the graph
		log("Tying input_points to the graph")
		self.list_tiedPoints = self.director.makeGraph(self.builder, [feature.geometry().asPoint() for feature in self.points])
		#get the graph
		log("Build the graph")
		self.network = self.builder.graph()
		
	def calcDijkstra(self, startPoint):
		"""Calculates Dijkstra on whole network beginning from one startPoint. Returns a tuple of TreeId-Array and Cost-Array that match up with their indices ([tree],[cost]) """
		return QgsGraphAnalyzer.dijkstra(self.network, self.network.findVertex(startPoint),0)
		
	
	def checkComputabilityStatus(self):
		input_network_srid = self.input_network.crs().authid()
		input_points_srid = self.input_points.crs().authid()
		if input_network_srid == input_points_srid:
			log("Input datasets match in spatial reference:")
			log("NetworkCRS == PointCRS: %d == %d".format(input_network_srid, input_points_srid))
			AssignAnalysisCrs(self.network) #if srids match, assign network crs to object as AnalysisCrs
			return True 	
		else:
			log("Input datasets do not have the same spatial reference:")
			log("Network-dataset: %d".format(input_network_srid))
			log("Point-dataset: %d".format(input_points_srid))
			log("Please reproject input datasets so that they share the same spatial reference!")
			return False	
	
class QneatIsochroneCalculator(QneatBaseCalculator):
	
	def __init__(self, input_network, input_points, input_directionFieldId, input_directDirectionValue, input_reverseDirectionValue, input_bothDirectionValue, input_defaultDirection, iso_steps, output_interpolation_path, output_polygon_path):
		QneatBaseCalculator.__init__(self, input_network, input_points, input_directionFieldId, input_directDirectionValue, input_reverseDirectionValue, input_bothDirectionValue, input_defaultDirection)
		self.iso_steps = iso_steps #deal with outer sections in polygonization of multiple ISOs (one additional iso range that can be cut off)
		self.output_interpolation = output_interpolation_path
		self.output_polygons = output_polygon_path
	
	
	def minMergeIsoPoints(self):
		# [MAP] list of Points from input-layer --> dijkstra()--> list of pointlists
		# [ListComprehension] take list of pointlists and min merge them into one array
		#(= no for loop)
		for current_point in self.points:
			return 0
			
			
			
	def interpolateIsoPoints(self):	
		#calc TIN Interpolation 
		return 0
	
	
	def polygonize(self):
		return 0
	

class QneatODMatrixCalculator(QneatBaseCalculator):
	
	def __init__(self, input_network, input_points, input_directionFieldId, input_directDirectionValue, input_reverseDirectionValue, input_bothDirectionValue, input_defaultDirection, output_matrix):
		QneatBaseCalculator.__init__(self, input_network, input_points, input_directionFieldId, input_directDirectionValue, input_reverseDirectionValue, input_bothDirectionValue, input_defaultDirection)
		self.networkEnterCost = self.calcNetworkEnterCost()
		self.output_matrix = output_matrix
		
	
	def calcMatrix(self):
		
		self.list_input_points
		return None
	
	def calcNetworkEnterCost(self):
		return [input_point.geometry().distance(self.list_tiedPoints[i].geometry()) for i, input_point in enumerate(self.list_input_points)]
		
	

if __name__ == '__main__':
	IsoCalcObj = QneatIsochroneCalculator("graph", "points", "50/100/150/200", "interpolation_raster", "polygons")
	IsoCalcObj.CalcIsoPoints()
	#IsoCalcObj.getCrs("4325")
	print IsoCalcObj.iso_points
	print IsoCalcObj.crs
	print dir(IsoCalcObj)
