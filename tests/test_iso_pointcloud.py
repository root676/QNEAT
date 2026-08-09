# -*- coding: utf-8 -*-
"""
***************************************************************************
    test_iso_pointcloud.py
    ---------------------

    qneat:isoareaaspointcloudfrompoint    qneat:isoareaaspointcloudfromlayer

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

from qgis.core import Qgis
from qgis.PyQt.QtCore import QMetaType

from . import fixtures
from .oracle import nodeKey
from .qneat_testcase import (QneatTestCase, COORDINATE_TOLERANCE,
                             STRATEGY_DISTANCE, STRATEGY_TIME)

EXPECTED_FIELDS = ['vertex_id', 'cost', 'origin_point_id']

#c1r3, exactly on a network node
ORIGIN_ON_NODE = (300000.0, 62000.0)


class IsoPointcloudTestBase(QneatTestCase):

    def collect(self, features) -> dict:
        """Output points keyed by position, so they can be matched to the oracle."""
        collected = {}
        for feature in features:
            point = feature.geometry().constGet()
            key = nodeKey((point.x(), point.y()))
            self.assertNotIn(key, collected,
                             f'vertex {key} appears more than once in the pointcloud')
            collected[key] = feature
        return collected

    def assertCloudMatches(self, features, solved, origin_indices, max_cost,
                           strategy, origin_ids):
        """Every reachable vertex, once, with the cheapest cost and its origin."""
        expected = solved.isoPoints(origin_indices, max_cost)
        actual = self.collect(features)

        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        self.assertEqual(missing, [], f'{len(missing)} reachable vertices are missing')
        self.assertEqual(unexpected, [],
                         f'{len(unexpected)} vertices beyond the cost limit were emitted')

        for key, (cost, origin_index) in expected.items():
            feature = actual[key]
            self.assertCost(feature['cost'], cost, strategy, f'vertex {key}')
            self.assertEqual(feature['origin_point_id'], origin_ids[origin_index],
                             f'vertex {key}: attributed to the wrong origin')

            #the cost is also carried as the M value of the geometry
            point = feature.geometry().constGet()
            self.assertTrue(QgsWkbTypes_hasM(feature.geometry()),
                            f'vertex {key}: geometry should carry an M value')
            self.assertCost(point.m(), cost, strategy, f'vertex {key} M value')

        return expected


def QgsWkbTypes_hasM(geometry) -> bool:
    from qgis.core import QgsWkbTypes
    return QgsWkbTypes.hasM(geometry.wkbType())


class IsoPointcloudFromPointTest(IsoPointcloudTestBase):

    def run_pointcloud(self, origin, max_cost, strategy=STRATEGY_DISTANCE,
                       epsg=fixtures.METRIC_EPSG):
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'ORIGIN_POINT': f'{origin[0]},{origin[1]} [EPSG:{epsg}]',
            'MAX_COST': max_cost,
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        results = self.runAlgorithm('isoareaaspointcloudfrompoint', parameters)
        return results, self.solve([origin], strategy, epsg)

    def test_output_schema(self):
        results, _ = self.run_pointcloud(ORIGIN_ON_NODE, 1500.0)
        layer = self.outputLayer(results)
        self.assertFieldNames(layer, EXPECTED_FIELDS)
        self.assertEqual(layer.wkbType(), Qgis.WkbType.PointM)
        self.assertEqual(layer.crs().authid(), 'EPSG:32118')
        self.assertEqual(layer.fields().field('vertex_id').type(), QMetaType.Type.LongLong)
        self.assertEqual(layer.fields().field('cost').type(), QMetaType.Type.Double)

    def test_distance_cloud(self):
        #2100 m, not 2000: a grid edge is 1000.002 m on the ellipsoid, so a flat
        #2000 m budget stops just short of the second ring of nodes
        results, solved = self.run_pointcloud(ORIGIN_ON_NODE, 2100.0)
        expected = self.assertCloudMatches(self.outputFeatures(results), solved, [0],
                                           2100.0, STRATEGY_DISTANCE, {0: 0})
        #origin, three neighbours at one hop, four nodes at two hops
        self.assertGreaterEqual(len(expected), 8)
        #the origin itself is in there at zero cost
        self.assertCost(self.collect(self.outputFeatures(results))[nodeKey(ORIGIN_ON_NODE)]['cost'],
                        0.0, STRATEGY_DISTANCE, 'origin vertex')

    def test_time_cloud_reaches_further_along_fast_edges(self):
        results, solved = self.run_pointcloud(ORIGIN_ON_NODE, 300.0, STRATEGY_TIME)
        self.assertCloudMatches(self.outputFeatures(results), solved, [0],
                                300.0, STRATEGY_TIME, {0: 0})

        reached = self.collect(self.outputFeatures(results))
        #col 1 is a 100 km/h connector, row 3 out of the same node is 10 km/h,
        #so within 300 s the cloud must get further down column 1 than along row 3
        self.assertIn(nodeKey((300000.0, 60000.0)), reached,
                      'the fast column 1 connector should be fully traversed')
        self.assertNotIn(nodeKey((302000.0, 62000.0)), reached,
                         'two 10 km/h row 3 edges take 720 s, well beyond the limit')

    def test_cost_limit_is_inclusive_of_nothing_beyond_it(self):
        """Nothing over the limit, and lowering the limit only removes points."""
        wide, _ = self.run_pointcloud(ORIGIN_ON_NODE, 2500.0)
        narrow, _ = self.run_pointcloud(ORIGIN_ON_NODE, 1200.0)

        wide_points = self.collect(self.outputFeatures(wide))
        narrow_points = self.collect(self.outputFeatures(narrow))

        self.assertTrue(set(narrow_points).issubset(set(wide_points)),
                        'a smaller budget must yield a subset of the larger one')
        for key, feature in narrow_points.items():
            self.assertLessEqual(feature['cost'], 1200.0 + COORDINATE_TOLERANCE)
            self.assertCost(feature['cost'], wide_points[key]['cost'],
                            STRATEGY_DISTANCE, f'{key} cost is budget independent')

    def test_origin_beyond_its_own_entry_cost_yields_nothing(self):
        """An origin that cannot even reach the network produces no points."""
        origin = (299400.0, 59400.0)   # about 848 m off the network
        results, solved = self.run_pointcloud(origin, 100.0)
        self.assertEqual(self.outputFeatures(results), [])
        self.assertEqual(solved.isoPoints([0], 100.0), {})

    def test_detached_component_is_self_contained(self):
        """An origin on the detached square only ever sees the detached square."""
        origin = (310500.0, 70200.0)
        results, solved = self.run_pointcloud(origin, 5000.0)
        features = self.outputFeatures(results)
        self.assertCloudMatches(features, solved, [0], 5000.0, STRATEGY_DISTANCE, {0: 0})

        for feature in features:
            point = feature.geometry().constGet()
            self.assertGreater(point.x(), 309000.0,
                               'the grid must not appear in the detached cloud')


class IsoPointcloudFromLayerTest(IsoPointcloudTestBase):

    def run_pointcloud(self, max_cost, keep, id_field='id_int',
                       strategy=STRATEGY_DISTANCE, epsg=fixtures.METRIC_EPSG):
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'ORIGIN_POINTS': self.pointLayer('origins', epsg, keep=keep),
            'ORIGIN_ID_FIELD': id_field,
            'MAX_COST': max_cost,
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        results = self.runAlgorithm('isoareaaspointcloudfromlayer', parameters)

        points = [p for p in fixtures.origins(epsg) if p.id_int in keep]
        solved = self.solve([p.xy for p in points], strategy, epsg)
        return results, solved, points

    def test_multiple_origins_keep_the_cheapest_cost(self):
        keep = [1, 4]   # c1r3 and c5r4, at opposite ends of the grid
        results, solved, points = self.run_pointcloud(2500.0, keep)
        origin_ids = {index: point.id_int for index, point in enumerate(points)}

        expected = self.assertCloudMatches(self.outputFeatures(results), solved,
                                           list(range(len(points))), 2500.0,
                                           STRATEGY_DISTANCE, origin_ids)

        #both origins must actually have contributed, otherwise the test would
        #not be exercising the merge at all
        contributors = {origin_index for _, origin_index in expected.values()}
        self.assertEqual(contributors, {0, 1},
                         'both origins should own the vertices nearest to them')

    def test_string_origin_id_is_carried_through(self):
        keep = [1, 4]
        results, solved, points = self.run_pointcloud(1500.0, keep, id_field='id_str')
        layer = self.outputLayer(results)
        self.assertEqual(layer.fields().field('origin_point_id').type(),
                         QMetaType.Type.QString)

        origin_ids = {index: point.id_str for index, point in enumerate(points)}
        self.assertCloudMatches(list(layer.getFeatures()), solved,
                                list(range(len(points))), 1500.0,
                                STRATEGY_DISTANCE, origin_ids)

    def test_time_strategy_across_origins(self):
        keep = [1, 3, 4]
        results, solved, points = self.run_pointcloud(400.0, keep, strategy=STRATEGY_TIME)
        origin_ids = {index: point.id_int for index, point in enumerate(points)}
        self.assertCloudMatches(self.outputFeatures(results), solved,
                                list(range(len(points))), 400.0,
                                STRATEGY_TIME, origin_ids)

    def test_origins_in_separate_components(self):
        """Origins on both components cover both, without mixing costs."""
        keep = [1, 5]
        results, solved, points = self.run_pointcloud(2000.0, keep)
        origin_ids = {index: point.id_int for index, point in enumerate(points)}
        self.assertCloudMatches(self.outputFeatures(results), solved,
                                list(range(len(points))), 2000.0,
                                STRATEGY_DISTANCE, origin_ids)

        by_origin = {}
        for feature in self.outputFeatures(results):
            by_origin.setdefault(feature['origin_point_id'], []).append(
                feature.geometry().constGet().x())
        self.assertEqual(sorted(by_origin), [1, 5])
        self.assertLess(max(by_origin[1]), 309000.0, 'grid origin stays on the grid')
        self.assertGreater(min(by_origin[5]), 309000.0,
                           'detached origin stays on the detached square')
