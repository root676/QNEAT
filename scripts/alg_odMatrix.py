"""
***************************************************************************
    alg_odMatrix.py
    ---------------------
    Date                 : November 2017
    Copyright            : (C) 2017 by Clemens Raffler
    Email                : clemens dot raffler at gmail dot com
***************************************************************************
"""

##QNEAT tools=group
##Input_Network_Layer=vector
##Input_Point_Layer=vector
##Input_Point_IDField=field Input_Point_Layer
#Direction_Field= optional field
#Value_for_normal_Links=optional number
#Value_for reverse_Direction=optional number
#Value_for_bidirectional_Links=optional number
#Value_for_Default_Direction=optional number 3
##Output_Matrix_File=output table
"""
Input_Network_Layer="STRASSENGRAPHOGD" #input parameters return filepaths
Input_Point_Layer="POINTS"
Output_Matrix_File="C:\Matrix_File.csv"
"""
layer_name = "point"


from QNEAT.QneatFramework.QneatNetwork import QneatNetwork
from QNEAT.QneatFramework.QneatAnalysisPoint import QneatAnalysisPoint
from QNEAT.QneatFramework import QneatUtilities as util

 

def log(message):
    progress.setText(message)
    
    
log("Initializing QneatODMatrixCalculator")
net= QneatNetwork(input_network = Input_Network_Layer, input_points = Input_Point_Layer, input_pointIdField = Input_Point_IDField)



log("populating QneatAnalysisPoint List")
list_analysis_points = [QneatAnalysisPoint("point", feature, net.input_pointIdField, net.network, net.list_tiedPoints[i]) for i, feature in enumerate(util.getFeatures(net.input_points))]
log("population Done")

for point in list_analysis_points:
    log(point.__str__())
"""
dijkstra_query = net.calcDijkstra(list_analysis_points[0].network_vertex_id, 0)

log(str(len(dijkstra_query[0])))
log(str(len(dijkstra_query[1])))
"""


for start_point in list_analysis_points:
    dijkstra_query = net.calcDijkstra(start_point.network_vertex_id, 0)
    for query_point in list_analysis_points:
        if dijkstra_query[0][query_point.network_vertex_id] == -1:
            log("Path not found")
        else:
            """
            endpoint_array_index = dijkstra_query[0].index(query_point.network_vertex_id)
            cost_val = dijkstra_query[1][endpoint_array_index]
            """
            log(str(dijkstra_query[1][query_point.network_vertex_id]))

log("Initialization Done")
log("Ending Algorithm")

