class QneatGeometryException(Exception):
    def __init__(self, given_input, expected_input):
    
        geom_str_list = ["Point","Line","Polygon", "UnknownGeometry", "NoGeometry"]
        self.message = "Dataset has wrong geometry type. Got {} dataset but expected {} dataset instead. ".format(geom_str_list[int(repr(given_input))], geom_str_list[int(repr(expected_input))])

        super(QneatGeometryException, self).__init__(self.message)
        
class QneatCrsException(Exception):
    def __init__(self, *crs):
    
        self.message = "Coordinate Reference Systems don't match up: {} Reproject all datasets so that their CRSs match up.".format(list(crs))

        super(QneatCrsException, self).__init__(self.message)

