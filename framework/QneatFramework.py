

from qgis.core import *
from qgis.analysis import *
from qgis.networkanalysis import *

from PyQt4.QtCore import QVariant

from QneatUtilities import *

from processing.tools.dataobjects import getObjectFromUri

import gdal, ogr


class QneatBaseCalculator():
	
	
	"""
	QNEAT base-class:
	Provides basic logic for more advanced network analysis algorithms
	"""
	
	
	def __init__(self,
				 input_network,
				 input_points,
				 input_directionFieldId=None,
				 input_directDirectionValue=None,
				 input_reverseDirectionValue=None,
				 input_bothDirectionValue=None, 
				 input_defaultDirection=None):
		#init
		logPanel("__init__[QneatBaseCalculator]: setting up parameters")
		#init datsets
		logPanel("__init__[QneatBaseCalculator]: setting up datasets")
		self.input_network = getObjectFromUri(input_network)
		self.input_points = getObjectFromUri(input_points)
		
	
		#init computabiliyt and crs
		logPanel("__init__[QneatBaseCalculator]: checking computability")
		self.ComputabilityStatus = self.checkComputabilityStatus()
		
		if self.ComputabilityStatus == True:
			logPanel("__init__[QneatBaseCalculator]: computability OK")
			logPanel("__init__[QneatBaseCalculator]: setting up network analysis parameters")
			self.AnalysisCrs = self.setAnalysisCrs()
			
			#init direction fields
			self.directedAnalysis = self.checkIfDirected((input_directDirectionValue, input_reverseDirectionValue, input_bothDirectionValue, input_defaultDirection))
			if self.directedAnalysis == True:
				logPanel("...Analysis is directed")
				logPanel("...setting up Director")
				self.director = QgsLineVectorLayerDirector(self.input_network,
											input_directionFieldId,
											input_directDirectionValue,
											input_reverseDirectionValue,
											input_bothDirectionValue,
											input_defaultDirection)
			else:
				logPanel("...Analysis is undirected")
				logPanel("...defaulting to normal director")
				self.director = QgsLineVectorLayerDirector(self.input_network,
														 -1,
														 '',
														 '',
														 '',
														 3)
			
			#init graph analysis
			logPanel("__init__[QneatBaseCalculator]: setting up network analysis")
			logPanel("...getting all analysis points")
			self.list_input_points = self.input_points.getFeatures(QgsFeatureRequest().setFilterFids(self.input_points.allFeatureIds()))
		
			#Use distance as cost-strategy pattern.
			logPanel("...Setting distance as cost property")
			self.properter = QgsDistanceArcProperter()
			#add the properter to the QgsGraphDirector
			self.director.addProperter(self.properter)
			logPanel("...Setting the graph builders spatial reference")
			self.builder = QgsGraphBuilder(self.AnalysisCrs)
			#tell the graph-director to make the graph using the builder object and tie the start point geometry to the graph
			logPanel("...Tying input_points to the graph")
			self.list_tiedPoints = self.director.makeGraph(self.builder, getListOfPoints(self.input_points))
			#get the graph
			logPanel("...Build the graph")
			self.network = self.builder.graph()
			logPanel("__init__[QneatBaseCalculator]: init complete")
			
			
	def calcDijkstra(self, startPoint):
		"""Calculates Dijkstra on whole network beginning from one startPoint. Returns a tuple of TreeId-Array and Cost-Array that match up with their indices ([tree],[cost]) """
		return QgsGraphAnalyzer.dijkstra(self.network, self.network.findVertex(startPoint),0)
		
	
	def checkComputabilityStatus(self):
		input_network_srid = self.input_network.crs().authid()
		input_points_srid = self.input_points.crs().authid()
		if input_network_srid == input_points_srid:
			logPanel("...Input datasets match in spatial reference:")
			logPanel("...NetworkCRS == PointCRS: {} == {}".format(input_network_srid, input_points_srid))
			return True 	
		else:
			logPanel("...Input datasets do not have the same spatial reference:")
			logPanel("...Network-dataset: {}".format(input_network_srid))
			logPanel("...Point-dataset: {}".format(input_points_srid))
			logPanel("...Please reproject input datasets so that they share the same spatial reference!")
			return False
	
	def checkIfDirected(self, directionArgs):
		if directionArgs.count(None) == 0:
			return True
		else:
			return False
		
	def setAnalysisCrs(self):
		return self.input_network.crs()
			
	def setNetworkDirection(self, directionArgs):	
		if directionArgs.count(None) == 0:
			self.directedAnalysis = True
			self.directionFieldId, self.input_directDirectionValue, self.input_reverseDirectionValue, self.input_bothDirectionValue, self.input_defaultDirection = directionArgs
		else:
			self.directedAnalysis = False
		
class QneatIsochroneCalculator(QneatBaseCalculator):
	
	def __init__(self,
				input_network,
				input_points,
				iso_steps,
				output_interpolation_path,
				output_polygon_path,
				input_directionFieldId=None,
				input_directDirectionValue=None,
				input_reverseDirectionValue=None,
				input_bothDirectionValue=None,
				input_defaultDirection=None,
				):
		
		QneatBaseCalculator.__init__(self,
									input_network,
									input_points,
									input_directionFieldId,
									input_directDirectionValue,
									input_reverseDirectionValue,
									input_bothDirectionValue,
									input_defaultDirection)
		
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
	
	def __init__(self,
				input_network,
				input_points,
				output_matrix,
				input_directionFieldId=None,
				input_directDirectionValue=None,
				input_reverseDirectionValue=None,
				input_bothDirectionValue=None,
				input_defaultDirection=None
				):
		
		QneatBaseCalculator.__init__(self,
									input_network,
									input_points,
									input_directionFieldId,
									input_directDirectionValue,
									input_reverseDirectionValue,
									input_bothDirectionValue,
									input_defaultDirection)
		
		logPanel("__init__[QneatODMatrixCalculator]: setting up parameters")
		#self.networkEnterCost = self.calcNetworkEnterCost()
		self.output_matrix = output_matrix
		
	
	
	def calcMatrix(self):
		for point in self.list_tiedPoints:
			(tree, cost) = QgsGraphAnalyzer.dijkstra(self.network, self.network.findVertex(point), 0)
			for point in self.list_tiedPoints:
				[tree[i],cost[i] for point, i in enumerate(self.list_tiedPoints]

		return None
	"""
	def calcNetworkEnterCost(self):
		return [input_point.geometry().distance(self.list_tiedPoints[i].geometry()) for i, input_point in enumerate(self.list_input_points)]
	"""
	

