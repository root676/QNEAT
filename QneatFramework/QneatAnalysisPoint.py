"""
***************************************************************************
    QneatAnalysisPoint.py
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



class QneatAnalysisPoint():
    
    def __init__(self, layer_name, feature, point_id):
        self.layer_name = layer_name
        self.point_id = point_id
        self.point_geom = feature.geometry().asPoint()
        self.entry_cost = None
        self.netry_geom = None
        
    def calcEntryCost(self, network):
        #logic to calculate cost to nearest network entry point according to properter
        pass
    
    def calcEntryGeom(self, network):
        pass
    
    def getNearestNetworkNodeId(self):
        pass
    
    def getNearestNetworkNodeGeom(self):
        pass
    
    def getXCoord(self):
        return self.point_geom.x()
    
    def getYCoord(self):
        return self.point_geom.y()