##QNEAT tools=group
##Input_Network_Layer=vector
##Input_Point_Layer=vector
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
from QNEAT.framework import QneatUtilities as util
from QNEAT.framework.QneatFramework import QneatODMatrixCalculator


def log(message):
    progress.setText(message)
    
    
log("Initializing QneatODMatrixCalculator")
QneatODMatrixCalculator(
            input_network = Input_Network_Layer,
            input_points = Input_Point_Layer,
            output_matrix= Output_Matrix_File)


log("Initialization Done")
log("Ending Algorithm")


