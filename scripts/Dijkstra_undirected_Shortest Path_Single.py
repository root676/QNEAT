"""
***************************************************************************
    Undirected_OD_Matrix_as_Table.py
    ---------------------
    Date                 : December 2017
    Copyright            : (C) 2017 by Clemens Raffler
    Email                : clemens dot raffler at gmail dot com
***************************************************************************
"""

##QNEAT tools=group
##Input_From_Point_Layer=vector
##Input_Network_Layer=vector
##Input_To_Point_Layer=vector
##Output_Matrix_csv_File=output table
"""
Input_Network_Layer="STRASSENGRAPHOGD" #input parameters return filepaths
Input_Point_Layer="POINTS"
Output_Matrix_File="C:\Matrix_File.csv"
"""

import time

from QNEAT.QneatFramework.QneatNetwork import QneatNetwork
from QNEAT.QneatFramework.QneatAnalysisPoint import QneatAnalysisPoint
from QNEAT.QneatFramework import QneatUtilities as util

from processing.tools.dataobjects import getObjectFromUri
 
"""
logging functions:
Must remain in script file because progress variable is only available in processing context
"""
def log(message):
    progress.setText(message)
    
def setProgress(current_workstep_number, total_workload):
    progress.setPercentage(int((float(current_workstep_number)/total_workload)*100))

#obtain starting time for alg evaluation    
alg_start_time = time.time()
    
log("Initializing QneatNetwork")
net_layer = getObjectFromUri(Input_Network_Layer)
from_point_layer = getObjectFromUri(Input_Network_Layer)
to_point_layer = getObjectFromUri(Input_To_Point_Layer)
net= QneatNetwork(input_network = net_layer, input_points = to_point_layer)
log("Initialization done")

#implement layer name initialization
log("Initialize QneatAnalysisPoint list")
list_analysis_points = [QneatAnalysisPoint("point", feature, Input_unique_Point_ID_Field, net.network, net.list_tiedPoints[i]) for i, feature in enumerate(util.getFeatures(net.input_points))]
log("Population done")

#estimate total workload
total_workload = float(pow(len(list_analysis_points),2))
log("Expecting total workload of {} iterations".format(int(total_workload)))


log("Building Output Layer")
# create layer
output_layer = QgsVectorLayer("Line", "output_routing", "memory")
pr = output_layer.dataProvider()

# add fields
pr.addAttributes([QgsField("from_id", QVariant.String),
                    QgsField("to_id",  QVariant.String),
                    QgsField("cost", QVariant.Double)])
output_layer.updateFields() # tell the vector layer to fetch changes from the provider



# add a feature
fet = QgsFeature()
fet.setGeometry(QgsGeometry.fromPoint(QgsPoint(10,10)))
fet.setAttributes(["Johny", 2, 0.3])
pr.addFeatures([fet])

# update layer's extent when new features have been added
# because change of extent in provider is not propagated to the layer
vl.updateExtents()


#IMPLEMENT unrechable points properly
with open(Output_Matrix_csv_File, 'wb') as csvfile:
    csv_writer = csv.writer(csvfile, delimiter=';',
                                quotechar='|', 
                                quoting=csv.QUOTE_MINIMAL)
    #write header
    csv_writer.writerow(["origin_id","destination_id","cost"])
    
    current_workstep_number = 0
    
    for start_point in list_analysis_points:
        #optimize in case of undirected (not necessary to call calcDijkstra as it has already been calculated - can be replaced by reading from list)
        dijkstra_query = net.calcDijkstra(start_point.network_vertex_id, 0)
        for query_point in list_analysis_points:
            if (current_workstep_number%1000)==0:
                log("{} OD-pairs processed...".format(current_workstep_number))
            if query_point.point_id == start_point.point_id:
                csv_writer.writerow([start_point.point_id, query_point.point_id, float(0)])
            elif dijkstra_query[0][query_point.network_vertex_id] == -1:
                csv_writer.writerow([start_point.point_id, query_point.point_id, None])
            else:
                entry_cost = start_point.calcEntryCost("distance")+query_point.calcEntryCost("distance")
                total_cost = dijkstra_query[1][query_point.network_vertex_id]+entry_cost
                csv_writer.writerow([start_point.point_id, query_point.point_id, total_cost])
            current_workstep_number=current_workstep_number+1
            setProgress(current_workstep_number, total_workload)
            
    log("Total number of OD-pairs processed: {}".format(current_workstep_number))

    log("Initialization Done")
    log("Ending Algorithm")

#log duration to console
duration = time.time()- alg_start_time
log("Algorithm execution duration: {}".format(duration))
