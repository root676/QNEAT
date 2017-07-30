
##input_Network=vector
##input_Points=vector
##input_cost_type=string
##input_iso_steps=string
##output_isochrones=output vector

from PyQt4.QtCore import *
from PyQt4.QtGui import *


from qgis.core import *
from qgis.analysis import *
from qgis.gui import *
from qgis.networkanalysis import *

import gdal, ogr


import subprocess




"""------------------function definition--------------------"""
def getProjectCrs():
    return iface.mapCanvas().mapRenderer().destinationCrs()
    
def getLayerByName(input_name):    
    for lyr in QgsMapLayerRegistry.instance().mapLayers().values():
        if lyr.name() == input_name:
            return lyr
            break

def getFieldIndex(vector_layer, fieldname):
    return vector_layer.fields().indexFromName(fieldname)

def deleteFolderContent(shape_path):
    QgsVectorFileWriter.deleteShapeFile(shape_path)
    """
    driver = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(shape_path):
        driver.DeleteDataSource(shape_path)
    """
def populateQgsVectorLayer(vector_layer, ):

    #fill layer with points
    vector_layer.startEditing()
    for i, geometry in enumerate(geometry_list):
        feat = QgsFeature()
        feat.setGeometry(geometry)#geometry from point
        feat.setAttributes(attribute_list[i])
        vector_layer.addFeature(feat, True)
    vector_layer.commitChanges()
    
    return vector_layer

def queryNetworkVertices(graph_layer, source_point_layer): #returns a QgsVectorLayer containing all vertices in distance
    
    #direction can be added
    """setup network analysis"""
    #line director args: layer, directionFieldId, str directDirectionValue, str reverseDirectionValue, str bothDirectionValue, int defaultDirection
    director = QgsLineVectorLayerDirector(graph_layer, -1, '', '', '', 3)
    #Use distance as cost-strategy pattern.
    properter = QgsDistanceArcProperter()
    #add the properter to the QgsGraphDirector
    director.addProperter(properter)
    builder = QgsGraphBuilder(QgsCoordinateReferenceSystem(31256))

    #tell the graph-director to make the graph using the builder object and tie the start point geometry to the graph
    source_point_request = QgsFeatureRequest().setFilterFids(source_point_layer.allFeatureIds())
    source_point_features = source_point_layer.getFeatures(source_point_request)
    
    tiedPoints = director.makeGraph(builder, [feature.geometry().asPoint() for feature in source_point_features])
    #get the graph
    graph = builder.graph()


    #dijkstra method returns two arrays (lists):
    #first array: List of tree-indices of incoming edges or -1 if no incoming edges (eg. root node of tree)
    #second array: accumulated cost from root of the tree to vertex i or DOUBLE_MAX if vertex i is unreachable from the tree-root.


    #list to store costs of vertices
    vertex_cost = []
    
    iso_cost_dict = {}
    
    for current_point in tiedPoints:
        current_source_point_id = graph.findVertex(current_point)
        
        #query vertices for point
        (tree, cost) = QgsGraphAnalyzer.dijkstra(graph, current_source_point_id, 0)
        
        i = 0
        while i < len(cost):
          #as long as costs at vertex i is greater than iso_distance and there exists an incoming edge (tree[i]!=-1) 
          #consider it as a possible catchment polygon element
          if tree[i] != -1:
            outVertexId = graph.arc(tree [i]).outVertex()
            #if the costs of the current vertex are lower than the radius, append the vertex id to results.
            if cost[outVertexId] < iso_distance and outVertexId in iso_cost_dict:
                #if vertex already in dict, test if the new one has lower costs and replace old one
                if iso_cost_dict.get(outVertexId)[1] > cost[outVertexId]:
                    iso_cost_dict[outVertexId] = [QgsGeometry().fromPoint(graph.vertex(i).point()), cost[outVertexId]]
            elif cost[outVertexId] < iso_distance:
                #if vertex is not found in dict, add the current vertex to the dict.
                iso_cost_dict[outVertexId] = [QgsGeometry().fromPoint(graph.vertex(i).point()), cost[outVertexId]]
          #count up to next vertex
          i = i + 1
    
    """ TODO: Populate new layer from dict (not two lists"""
    URI = "Point?crs=EPSG:31256&field=cost:real&index=yes"
    vl = QgsVectorLayer(URI, "catchment_points", "memory")

    # fill layer with points
    vl.startEditing()
    for vertex_id in iso_cost_dict:
        feat = QgsFeature()
        feat.setGeometry(iso_cost_dict.get(vertex_id)[0])  # geometry from point
        feat.setAttributes([iso_cost_dict.get(vertex_id)[1]])
        vl.addFeature(feat, True)
    vl.commitChanges()
    
    QgsMapLayerRegistry.instance().addMapLayer(vl, True)
    
    return vl

def interpolateDistanceTIN(layer, export_path, resolution):
    layer_data = qgis.analysis.QgsInterpolator.LayerData()
    layer_data.vectorLayer = layer
    layer_data.zCoordInterpolation=False
    layer_data.InterpolationAttribute =0
    layer_data.mInputType = 1

    tin_interpolator = qgis.analysis.QgsTINInterpolator([layer_data])

    rect = layer.extent()
    ncol = int( ( rect.xMaximum() - rect.xMinimum() ) / resolution )
    nrows = int( (rect.yMaximum() - rect.yMinimum() ) / resolution)
    test = qgis.analysis.QgsGridFileWriter(tin_interpolator,export_path,rect,ncol, nrows,resolution,resolution)
    test.writeFile(True)          #Creating .asc raster 
    return QgsRasterLayer(export_path,"temp_interpolation",True)


def calcRaster(raster_layer, raster_name, syntax, band_number, export_path):
    #prepare raster calculator logic
    calc_entry = QgsRasterCalculatorEntry()
    calc_entry.ref = raster_name + "@1"
    calc_entry.raster = raster_layer
    calc_entry.bandNumber = band_number

    calculator_entries = [calc_entry]

    calc = QgsRasterCalculator(syntax, export_path, 'GTiff', raster_layer.extent(),raster_layer.width(),raster_layer.height(),calculator_entries)
    result_msg = calc.processCalculation()

    
def buildGDALRasterCalcCall(iso_step,input_path,export_path):
    return 'gdal_calc.bat --calc="A<={0}" --format GTiff --type Float32 -A {1} --A_band 1 --outfile {2}'.format(iso_step,input_path,export_path)

def buildGDALPolygonizeCall(input_path, export_path, layer_name, target_field_name):
    return 'gdal_polygonize.bat -mask {0} {0} -f "ESRI Shapefile" {1} {2} {3}'.format(input_path, export_path, layer_name, target_field_name) 
    
def cleanPolygon(polygon_layer): #returns geometry of cleaned polygon
    
    #variables for storing information about the largest iso-polygon
    big_poly_fid = None
    big_poly_geom = None
    max_area = None
    #TODO: Implement variables for iso-area attributes
    
    #logic to retrieve biggest polygon
    #check how many features are inside the layer
    feature_id_list = polygon_layer.allFeatureIds()
    #request features regardless of their quantity
    request = QgsFeatureRequest().setFilterFids(feature_id_list)
    #get all requested features
    requested_features = polygon_layer.getFeatures(request)
    #print "ISLAND REMOVAL"
    if len(feature_id_list) > 1: #if more than one polyogn exists, get the one with the biggest area
        #print "removing islands:" +str(len(feature_id_list)-1)
        for feature in requested_features:
            current_area = feature.geometry().area()
            if max_area == None or max_area < current_area:
                big_poly_fid = feature.id()
                big_poly_geom = feature.geometry().asPolygon()
                max_area = current_area
                #print current_area
            continue
    else: #if there is just one polygon, get the first polygon
        #print "no islands"
        biggest_feature = next(requested_features)
        big_poly_fid = biggest_feature.id()
        big_poly_geom = biggest_feature.geometry().asPolygon()
        max_area = biggest_feature.geometry().area()
        #print max_area

    #cleaned_geom = deleteRingsInPolygon(big_poly_geom)
    return_geometry = QgsGeometry().fromPolygon(big_poly_geom)
    return return_geometry

    
def deleteRingsInPolygon(polygon_geometry):
    #warning: does not handle multipolygons
    ring_count = len(polygon_geometry.asPolygon())
    #print polygon_geometry.asPolygon()
    #print "RING REMOVAL"

    if ring_count > 1:
        #print "polygon count: "+str(ring_count)
        i = 1
        while i < ring_count:
            #print "deleting ring "+str(i)
            #always delete second ring, the other rings will take the place of the second one in the next loop
            #print polygon_geometry.deleteRing(1,0)
            i += 1
        
    return_geometry_list = polygon_geometry
    
    
    return return_geometry_list
    
    

"""--------------end of function definition----------------"""



"""-------------------variable definition-------------------"""

#prepare linput ayers
origin_point_layer = getLayerByName("carsharing_mgi")
graph_layer = getLayerByName("STRASSENGRAPH")

#network analysis parameters
#start_point = QgsPoint(707.21886, 342100.50002)
#start_point2 = QgsPoint(2991.0,336953.0)

iso_distance = 2000
#iso_steps = [250,500,750,1000,1250,1500,1750]
iso_steps = [1750,1500,1250,1000,750,500,250]
iso_step = 500

#tin interpolationAttribute
tin_export_path = "S:/GIS_Workbench_S/script_output/interpolation.asc"

#raster reclassification
qgis_raster_calculator_syntax = '"tin@1"<={0}'.format(iso_step) #'(tin@1<={0})*1'.format(iso_step)
gdal_raster_calculator_syntax = "A<={0}".format(iso_step)
raster_calculator_export_path = "S:/GIS_Workbench_S/script_output/reclassified_raster.tif"

#polygonization
polygonize_export_basepath = "S:/GIS_Workbench_S/script_output/polygonize/"
polygonize_export_path = "S:/GIS_Workbench_S/script_output/polygonize/gdal_polygonized_raster.shp"


"""---------------end of variable definition---------------"""

"""----------------------main program--------------------"""
geom_list = []
attribute_list=[]

POLYGON_URI = "Polygon?crs=EPSG:31256&field=OBJECTID:real&field=iso:integer&index=yes"

output_vector_layer = QgsVectorLayer("Polygon", "isocrones", "memory")
output_provider = output_vector_layer.dataProvider()


output_provider.addAttributes([QgsField('fid',QVariant.Int),QgsField("origin_point_id", QVariant.Double),QgsField("iso", QVariant.Int)])
output_vector_layer.updateFields()

QgsMapLayerRegistry.instance().addMapLayer(output_vector_layer, True)

vertex_layer = queryNetworkVertices(graph_layer, origin_point_layer)

interpolated_distance_raster = interpolateDistanceTIN(vertex_layer, tin_export_path, 10)

for iso_class in iso_steps:
    print iso_class
    calcRaster(interpolated_distance_raster, "tin", '"tin@1"<={0}'.format(iso_class), 1, raster_calculator_export_path)

    #print"GDAL Polygonize"
    gdal_current_filename = "gdal_polygonized_raster_oid{0}_iso{1}.shp".format(1, iso_class)
    polygonize_export_path = polygonize_export_basepath+gdal_current_filename
    gdal_Polygonize_command = buildGDALPolygonizeCall(raster_calculator_export_path, polygonize_export_path, 'catchment_area', 'DN')
    subprocess.call(gdal_Polygonize_command, shell=True)
    #print"GDAL Polygonize ok"

    polygonized_catchment_area = QgsVectorLayer(polygonize_export_path,'catchment_area_oid{0}_iso{1}'.format(1, iso_class),'ogr')
    #QgsMapLayerRegistry.instance().addMapLayer(polygonized_catchment_area, True)

    cleaned_polygon_geometry = cleanPolygon(polygonized_catchment_area)
    #print gdal_current_filename
    #QgsMapLayerRegistry.instance().removeMapLayer(polygonized_catchment_area.id())
    #del polygonized_catchment_area
    #print"Cleaning Polygon ok"
    geom_list.append(cleaned_polygon_geometry)
    attribute_list.append([1, 1, iso_class])
        
for element_id, geometrieobjekt in enumerate(geom_list):
    iso_feat = QgsFeature()
    iso_feat.setGeometry(geometrieobjekt)
    iso_feat.setAttributes(attribute_list[element_id])
    output_vector_layer.startEditing()
    output_vector_layer.addFeatures([iso_feat])
    output_vector_layer.commitChanges()
    output_vector_layer.updateExtents()





