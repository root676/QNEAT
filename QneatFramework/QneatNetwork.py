"""
***************************************************************************
    QneatNetwork.py
    ---------------------
    Date                 : November 2017
    Copyright            : (C) 2017 by Clemens Raffler
    Email                : clemens dot raffler at gmail dot com
***************************************************************************
"""

from qgis.core import *
from qgis.analysis import *
from qgis.networkanalysis import *

from PyQt4.QtCore import QVariant

from QneatUtilities import *
from QneatExceptions import QneatGeometryException, QneatCrsException

from processing.tools.dataobjects import getObjectFromUri

import gdal, ogr
    

class QneatNetwork():
    
    
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

        logPanel("__init__[QneatBaseCalculator]: setting up parameters")


        logPanel("__init__[QneatBaseCalculator]: setting up datasets")
        
        #init datasets and check for right geometry
        layer = getObjectFromUri(input_network)
        if isGeometryType(layer, QGis.Line):
            self.input_network = getObjectFromUri(input_network)
        else:
            logPanel("ERROR: Network layer should be dataset layer")
            raise QneatGeometryException(layer.geometryType(), QGis.Line)
        
        layer = getObjectFromUri(input_points)
        if isGeometryType(layer, QGis.Point):
            self.input_points = layer
        else:
            logPanel("ERROR: Point layer should be point dataset")
            raise QneatGeometryException(layer.geometryType(), QGis.Point)
        del layer
        
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
                
            
    def calcDijkstra(self, startpoint_id, criterion):
        """Calculates Dijkstra on whole network beginning from one startPoint. Returns a list containing a TreeId-Array and Cost-Array that match up with their indices [[tree],[cost]] """
        tree, cost = QgsGraphAnalyzer.dijkstra(self.network, startpoint_id, criterion)
        dijkstra_query = list()
        dijkstra_query.insert(0, tree)
        dijkstra_query.insert(1, cost)
        return dijkstra_query
    
    def calcShortestTree(self, startpoint_id, criterion):
        tree = QgsGraphAnalyzer.shortestTree(self.network, startpoint_id, criterion)
        return tree
        
    
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
            raise QneatCrsException(input_network_srid, input_points_srid)
    
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

