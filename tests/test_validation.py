# -*- coding: utf-8 -*-
"""
***************************************************************************
    test_validation.py
    ---------------------

    The guards: what the algorithms refuse, and what they say when they do.

    Date                 : August 2026
    Copyright            : (C) 2026 by Clemens Raffler
    Email                : clemens dot raffler at gmail dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
from __future__ import annotations

from qgis.core import (QgsCoordinateTransform,
                       QgsFeature,
                       QgsProcessingException,
                       QgsProject,
                       QgsVectorLayer)

from . import fixtures
from .oracle import DISTANCE, TIME
from .qneat_testcase import (QneatTestCase, DEFAULT_SPEED,
                             ISO_METHOD_EUCLIDEAN, ISO_METHOD_TIN,
                             ISO_TYPE_POLYGONS, STRATEGY_DISTANCE, STRATEGY_TIME)

GEOGRAPHIC_EPSG = 4326


class ValidationTest(QneatTestCase):

    def reprojected(self, layer, epsg: int) -> QgsVectorLayer:
        """The same layer in another CRS, for the CRS guard tests."""
        target = fixtures.crs(epsg)
        transform = QgsCoordinateTransform(layer.crs(), target,
                                           QgsProject.instance().transformContext())

        geometry_type = 'LineString' if layer.geometryType() == 1 else 'Point'
        definition = '&'.join(
            [f'{geometry_type}?crs=EPSG:{epsg}'] +
            [f'field={field.name()}:{"double" if field.isNumeric() else "string"}'
             for field in layer.fields()])
        reprojected = QgsVectorLayer(definition, f'{layer.name()}_{epsg}', 'memory')

        features = []
        for source in layer.getFeatures():
            geometry = source.geometry()
            geometry.transform(transform)
            feature = QgsFeature(reprojected.fields())
            feature.setGeometry(geometry)
            feature.setAttributes(source.attributes())
            features.append(feature)
        reprojected.dataProvider().addFeatures(features)
        reprojected.updateExtents()

        self._layers.append(reprojected)
        return reprojected

    # ------------------------------------------------------------- numeric guards

    def test_zero_contour_interval_is_rejected(self):
        """A zero interval would ask for an unbounded number of contour levels."""
        parameters = self.baseParameters()
        parameters.update({
            'ORIGIN_POINT': '302000,61000 [EPSG:32118]',
            'ISO_AREA_METHOD': ISO_METHOD_EUCLIDEAN,
            'ISO_AREA_TYPE': ISO_TYPE_POLYGONS,
            'MAX_COST': 2000.0,
            'INTERVAL': 0.0,
            'CELL_SIZE': 100.0,
            'OUTPUT_COST_SURFACE': self.outputPath('surface'),
            'OUTPUT_ISO_AREAS': 'TEMPORARY_OUTPUT',
        })
        self.assertAlgorithmRaises('isoareafrompoint', parameters,
                                   'contour interval')

    def test_non_positive_cell_size_is_rejected(self):
        parameters = self.baseParameters()
        parameters.update({
            'ORIGIN_POINT': '302000,61000 [EPSG:32118]',
            'MAX_COST': 2000.0,
            'ISO_AREA_METHOD': ISO_METHOD_TIN,
            'CELL_SIZE': 0.0,
            'OUTPUT': self.outputPath('surface'),
        })
        #the parameter itself declares a positive minimum, so this is refused
        #before QNEAT's own guard in calcIsoTinInterpolation is reached
        self.assertAlgorithmRaises('isoareaascostsurfacefrompoint', parameters)

    def test_time_strategy_rejects_a_zero_default_speed(self):
        """Every entry cost divides by the default speed, so zero cannot pass."""
        parameters = self.baseParameters(strategy=STRATEGY_TIME)
        parameters['DEFAULT_SPEED'] = 0.0
        parameters.update({
            'START_POINT': '302000,61000 [EPSG:32118]',
            'END_POINT': '304000,62000 [EPSG:32118]',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        self.assertAlgorithmRaises('shortestpathbetweenpoints', parameters)

    def test_core_guards_zero_default_speed_directly(self):
        """The framework's own guard, which the parameter minimum hides.

        QgsProcessingParameterNumber refuses a zero default speed before
        processAlgorithm runs, so QneatCore's check is only reachable when the
        framework is driven directly - as any code embedding QNEAT would.
        """
        import importlib
        from . import qgis_bootstrap
        from qgis.core import QgsPointXY, QgsProcessingFeedback

        framework = importlib.import_module(
            f'{qgis_bootstrap.PLUGIN_PACKAGE}.QneatFramework')
        utilities = importlib.import_module(
            f'{qgis_bootstrap.PLUGIN_PACKAGE}.QneatUtilities')
        QneatCore = framework.QneatCore
        OptimizationStrategy = framework.OptimizationStrategy
        ProgressRange = framework.ProgressRange
        getFeatureFromPoint = utilities.getFeatureFromPoint

        network = self.networkLayer()
        points = [getFeatureFromPoint(0, QgsPointXY(302000.0, 61000.0))]

        from qgis.analysis import QgsVectorLayerDirector

        #defaultDirection has to be passed explicitly: QneatCore declares it
        #optional but builds QgsVectorLayerDirector.Direction(None) from it
        #unconditionally, which raises before any of its own guards run
        with self.assertRaises(QgsProcessingException) as caught:
            QneatCore(network, points, OptimizationStrategy.TIME, 'speed_kmh', 0.0,
                      0.0, ProgressRange(QgsProcessingFeedback(), 0.0, 1.0),
                      None, None, None, None,
                      int(QgsVectorLayerDirector.Direction.DirectionBoth))
        self.assertIn('default speed', str(caught.exception).lower())

    def test_oracle_agrees_that_zero_speed_is_invalid(self):
        """The reference implementation refuses the same thing, for the same reason."""
        with self.assertRaises(ValueError):
            fixtures.referenceNetwork().solve([(302000.0, 61000.0)], TIME, 0.0)
        #and the distance strategy does not care about speed at all
        fixtures.referenceNetwork().solve([(302000.0, 61000.0)], DISTANCE, 0.0)

    # ----------------------------------------------------------------- CRS guards

    def test_point_layer_in_a_different_crs_is_rejected(self):
        parameters = self.baseParameters()
        parameters.update({
            'POINTS': self.pointLayer('origins', fixtures.FOOT_EPSG),
            'ID_FIELD': 'id_int',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        message = self.assertAlgorithmRaises('odmatrixfrompointsastable', parameters,
                                             "doesn't match up")
        self.assertIn('EPSG:32118', str(message))
        self.assertIn('EPSG:2263', str(message))

    def test_destination_layer_in_a_different_crs_is_named_in_the_error(self):
        """The m:n algorithms say which of the two layers is the wrong one."""
        parameters = self.baseParameters()
        parameters.update({
            'ORIGIN_POINT_LAYER': self.pointLayer('origins', fixtures.METRIC_EPSG),
            'ORIGIN_ID_FIELD': 'id_int',
            'DESTINATION_POINT_LAYER': self.pointLayer('destinations',
                                                       fixtures.FOOT_EPSG),
            'DESTINATION_ID_FIELD': 'id_int',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        message = self.assertAlgorithmRaises('odmatrixfromlayersastable', parameters,
                                             'destination point layer')
        self.assertIn('EPSG:2263', str(message))

    def test_origin_layer_in_a_different_crs_is_named_in_the_error(self):
        parameters = self.baseParameters()
        parameters.update({
            'ORIGIN_POINT_LAYER': self.pointLayer('origins', fixtures.FOOT_EPSG),
            'ORIGIN_ID_FIELD': 'id_int',
            'DESTINATION_POINT_LAYER': self.pointLayer('destinations',
                                                       fixtures.METRIC_EPSG),
            'DESTINATION_ID_FIELD': 'id_int',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        self.assertAlgorithmRaises('odmatrixfromlayersastable', parameters,
                                   'origin point layer')

    def test_tin_interpolation_refuses_a_geographic_crs(self):
        """TIN interpolation is only meaningful on a projected CRS."""
        network = self.reprojected(self.networkLayer(), GEOGRAPHIC_EPSG)
        parameters = {
            'GRAPH_LAYER': network,
            'STRATEGY': STRATEGY_DISTANCE,
            'SPEED_FIELD': 'speed_kmh',
            'DEFAULT_SPEED': DEFAULT_SPEED,
            'TOLERANCE': 0.0,
            'ORIGIN_POINT': f'-73.9526,40.7166 [EPSG:{GEOGRAPHIC_EPSG}]',
            'MAX_COST': 2000.0,
            'INTERVAL': 500.0,
            'ISO_AREA_METHOD': ISO_METHOD_TIN,
            'ISO_AREA_TYPE': ISO_TYPE_POLYGONS,
            #a cell size in degrees. Note that the two cost surface algorithms
            #declare a minimum cell size of 1, which no geographic CRS can
            #satisfy sensibly, so this guard is only reachable through the
            #iso area algorithms, whose minimum is 0.0000001.
            'CELL_SIZE': 0.001,
            'MAX_OFF_GRAPH_TRAVEL_COST': 0.0,
            'OUTPUT_COST_SURFACE': self.outputPath('geographic_surface'),
            'OUTPUT_ISO_AREAS': 'TEMPORARY_OUTPUT',
        }
        self.assertAlgorithmRaises('isoareafrompoint', parameters,
                                   'projected coordinate system')

    def test_a_geographic_crs_still_routes(self):
        """Only the interpolation is restricted; routing itself is not."""
        network = self.reprojected(self.networkLayer(), GEOGRAPHIC_EPSG)
        parameters = {
            'GRAPH_LAYER': network,
            'STRATEGY': STRATEGY_DISTANCE,
            'SPEED_FIELD': 'speed_kmh',
            'DEFAULT_SPEED': DEFAULT_SPEED,
            'TOLERANCE': 0.0,
            'START_POINT': f'-74.0,40.70698 [EPSG:{GEOGRAPHIC_EPSG}]',
            'END_POINT': f'-73.95265,40.73399 [EPSG:{GEOGRAPHIC_EPSG}]',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        }
        feature = self.outputFeatures(
            self.runAlgorithm('shortestpathbetweenpoints', parameters))[0]

        #costs stay in real metres whatever the CRS, so the answer is still the
        #same order of magnitude as the projected run over the same grid
        self.assertGreater(feature['total_cost'], 1000.0)
        self.assertLess(feature['total_cost'], 20000.0)
