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

from QneatFramework import QneatNetwork, QneatAnalysisPoint, QneatUtilities as util


def log(message):
    progress.setText(message)
    
    
log("Initializing QneatODMatrixCalculator")
QneatNetwork(
            input_network = Input_Network_Layer,
            input_points = Input_Point_Layer)



log("Initialization Done")
log("Ending Algorithm")


