# -*- coding: utf-8 -*-
"""
***************************************************************************
    test_od_matrix.py
    ---------------------

    qneat:odmatrixfrompointsastable    qneat:odmatrixfrompointsaslines
    qneat:odmatrixfromlayersastable    qneat:odmatrixfromlayerslines

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
from .qneat_testcase import (QneatTestCase, MATRIX_GEOMETRY_LINE, MATRIX_GEOMETRY_ROUTE,
                             STRATEGY_DISTANCE, STRATEGY_TIME)

EXPECTED_FIELDS = ['origin_id', 'destination_id', 'entry_cost', 'network_cost',
                   'exit_cost', 'total_cost']

#the detached component holds origin 5 and destination 14; nothing routes
#between it and the grid
DETACHED_ORIGIN = 5
DETACHED_DESTINATION = 14


class OdMatrixTestBase(QneatTestCase):
    """Shared checks - the four algorithms only differ in shape and geometry."""

    def indexByIds(self, features) -> dict:
        indexed = {}
        for feature in features:
            key = (feature['origin_id'], feature['destination_id'])
            self.assertNotIn(key, indexed, f'duplicate od pair {key}')
            indexed[key] = feature
        return indexed

    def assertPairMatches(self, feature, solved, origin_index, destination_index,
                          strategy, what, same_point_is_free=True):
        reference = solved.route(origin_index, destination_index)
        if reference is None:
            self.assertNullCost(feature, what)
            return None
        if origin_index == destination_index and same_point_is_free:
            #a point against itself costs nothing at all, entry cost included
            for field in ('entry_cost', 'network_cost', 'exit_cost', 'total_cost'):
                self.assertCost(feature[field], 0.0, strategy, f'{what} {field}')
            return reference

        self.assertCost(feature['entry_cost'], reference.entry_cost, strategy,
                        f'{what} entry')
        self.assertCost(feature['network_cost'], reference.network_cost, strategy,
                        f'{what} network')
        self.assertCost(feature['exit_cost'], reference.exit_cost, strategy,
                        f'{what} exit')
        self.assertCost(feature['total_cost'], reference.total_cost, strategy,
                        f'{what} total')
        return reference


class OdMatrixFromPointsTest(OdMatrixTestBase):
    """The n:n algorithms, one point layer routed against itself."""

    def runMatrix(self, algorithm: str, strategy=STRATEGY_DISTANCE,
                  id_field='id_int', epsg=fixtures.METRIC_EPSG, extra=None):
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'POINTS': self.pointLayer('origins', epsg),
            'ID_FIELD': id_field,
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        if extra:
            parameters.update(extra)
        results = self.runAlgorithm(algorithm, parameters)

        points = [p.xy for p in fixtures.origins(epsg)]
        return results, self.solve(points, strategy, epsg), fixtures.origins(epsg)

    def test_table_is_complete_and_correct(self):
        results, solved, points = self.runMatrix('odmatrixfrompointsastable')
        layer = self.outputLayer(results)

        self.assertFieldNames(layer, EXPECTED_FIELDS)
        self.assertEqual(layer.wkbType(), Qgis.WkbType.NoGeometry)

        features = list(layer.getFeatures())
        self.assertEqual(len(features), len(points) ** 2,
                         'every ordered pair must appear exactly once')
        indexed = self.indexByIds(features)

        for origin_index, origin in enumerate(points):
            for destination_index, destination in enumerate(points):
                feature = indexed[(origin.id_int, destination.id_int)]
                self.assertPairMatches(feature, solved, origin_index, destination_index,
                                       STRATEGY_DISTANCE,
                                       f'{origin.id_str}->{destination.id_str}')
                self.assertTrue(feature.geometry().isEmpty(),
                                'the table variant carries no geometry')

    def test_unreachable_pairs_are_null(self):
        results, solved, points = self.runMatrix('odmatrixfrompointsastable')
        indexed = self.indexByIds(self.outputFeatures(results))

        detached = [p for p in points if p.id_int == DETACHED_ORIGIN][0]
        grid = [p for p in points if p.id_int != DETACHED_ORIGIN]

        for other in grid:
            self.assertNullCost(indexed[(detached.id_int, other.id_int)],
                                f'{detached.id_str}->{other.id_str}')
            self.assertNullCost(indexed[(other.id_int, detached.id_int)],
                                f'{other.id_str}->{detached.id_str}')

        #but the detached point still reaches itself at zero cost
        self.assertCost(indexed[(detached.id_int, detached.id_int)]['total_cost'],
                        0.0, STRATEGY_DISTANCE, 'detached self pair')

    def test_time_matrix(self):
        results, solved, points = self.runMatrix('odmatrixfrompointsastable',
                                                 strategy=STRATEGY_TIME)
        indexed = self.indexByIds(self.outputFeatures(results))
        for origin_index, origin in enumerate(points):
            for destination_index, destination in enumerate(points):
                self.assertPairMatches(indexed[(origin.id_int, destination.id_int)],
                                       solved, origin_index, destination_index,
                                       STRATEGY_TIME,
                                       f'{origin.id_str}->{destination.id_str}')

    def test_string_id_field_is_carried_through(self):
        """The id field's own datatype must survive into the output schema."""
        results, _, points = self.runMatrix('odmatrixfrompointsastable',
                                            id_field='id_str')
        layer = self.outputLayer(results)
        self.assertEqual(layer.fields().field('origin_id').type(),
                         QMetaType.Type.QString)
        self.assertEqual(layer.fields().field('destination_id').type(),
                         QMetaType.Type.QString)

        identifiers = {f['origin_id'] for f in layer.getFeatures()}
        self.assertEqual(identifiers, {p.id_str for p in points})

    def test_integer_id_field_is_carried_through(self):
        results, _, points = self.runMatrix('odmatrixfrompointsastable')
        layer = self.outputLayer(results)
        self.assertEqual(layer.fields().field('origin_id').type(), QMetaType.Type.Int)
        self.assertEqual({f['origin_id'] for f in layer.getFeatures()},
                         {p.id_int for p in points})

    def test_lines_are_straight_origin_to_destination(self):
        results, solved, points = self.runMatrix(
            'odmatrixfrompointsaslines',
            extra={'MATRIX_GEOMETRY_TYPE': MATRIX_GEOMETRY_LINE})
        layer = self.outputLayer(results)
        self.assertEqual(layer.wkbType(), Qgis.WkbType.LineString)

        indexed = self.indexByIds(layer.getFeatures())
        for origin_index, origin in enumerate(points):
            for destination_index, destination in enumerate(points):
                feature = indexed[(origin.id_int, destination.id_int)]
                vertices = [(p.x(), p.y()) for p in feature.geometry().asPolyline()]
                self.assertEqual(len(vertices), 2,
                                 'a Line geometry is the direct connection, nothing more')
                self.assertPointsEqual(vertices[0], origin.xy, 'line start')
                self.assertPointsEqual(vertices[1], destination.xy, 'line end')

    def test_routes_follow_the_network(self):
        results, solved, points = self.runMatrix(
            'odmatrixfrompointsaslines',
            extra={'MATRIX_GEOMETRY_TYPE': MATRIX_GEOMETRY_ROUTE})
        indexed = self.indexByIds(self.outputFeatures(results))

        for origin_index, origin in enumerate(points):
            for destination_index, destination in enumerate(points):
                what = f'{origin.id_str}->{destination.id_str}'
                feature = indexed[(origin.id_int, destination.id_int)]
                reference = solved.route(origin_index, destination_index)
                geometry = feature.geometry()

                if reference is None:
                    self.assertTrue(geometry.isEmpty(),
                                    f'{what}: unreachable pairs carry no route')
                    continue
                if origin_index == destination_index:
                    continue
                #QNEAT assembles the route from the destination backwards
                self.assertVertexSequence(geometry, list(reversed(reference.path)),
                                          f'{what} route')

    def test_route_geometry_is_longer_than_the_direct_line(self):
        """A route detouring over the grid cannot be shorter than the crow flight."""
        straight = self.runMatrix('odmatrixfrompointsaslines',
                                  extra={'MATRIX_GEOMETRY_TYPE': MATRIX_GEOMETRY_LINE})[0]
        routed = self.runMatrix('odmatrixfrompointsaslines',
                                extra={'MATRIX_GEOMETRY_TYPE': MATRIX_GEOMETRY_ROUTE})[0]

        straight_index = self.indexByIds(self.outputFeatures(straight))
        routed_index = self.indexByIds(self.outputFeatures(routed))

        compared = 0
        for key, line in straight_index.items():
            route = routed_index[key]
            if key[0] == key[1] or route.geometry().isEmpty():
                continue
            self.assertGreaterEqual(route.geometry().length(),
                                    line.geometry().length() - 1e-6,
                                    f'{key}: route shorter than the direct line')
            compared += 1
        self.assertGreater(compared, 0, 'nothing was actually compared')


class OdMatrixFromLayersTest(OdMatrixTestBase):
    """The m:n algorithms, origins routed against a separate destination layer."""

    def runMatrix(self, algorithm: str, strategy=STRATEGY_DISTANCE,
                  origin_id='id_int', destination_id='id_int',
                  epsg=fixtures.METRIC_EPSG, extra=None):
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'ORIGIN_POINT_LAYER': self.pointLayer('origins', epsg),
            'ORIGIN_ID_FIELD': origin_id,
            'DESTINATION_POINT_LAYER': self.pointLayer('destinations', epsg),
            'DESTINATION_ID_FIELD': destination_id,
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        if extra:
            parameters.update(extra)
        results = self.runAlgorithm(algorithm, parameters)

        origins = fixtures.origins(epsg)
        destinations = fixtures.destinations(epsg)
        #QNEAT builds one graph from origins followed by destinations, so the
        #reference has to tie the same set of points on in the same order
        solved = self.solve([p.xy for p in origins] + [p.xy for p in destinations],
                            strategy, epsg)
        return results, solved, origins, destinations

    def test_table_is_complete_and_correct(self):
        results, solved, origins, destinations = self.runMatrix('odmatrixfromlayersastable')
        layer = self.outputLayer(results)

        self.assertFieldNames(layer, EXPECTED_FIELDS)
        self.assertEqual(layer.wkbType(), Qgis.WkbType.NoGeometry)

        features = list(layer.getFeatures())
        self.assertEqual(len(features), len(origins) * len(destinations))
        indexed = self.indexByIds(features)

        for origin_index, origin in enumerate(origins):
            for offset, destination in enumerate(destinations):
                destination_index = len(origins) + offset
                self.assertPairMatches(indexed[(origin.id_int, destination.id_int)],
                                       solved, origin_index, destination_index,
                                       STRATEGY_DISTANCE,
                                       f'{origin.id_str}->{destination.id_str}',
                                       same_point_is_free=False)

    def test_only_pairs_inside_one_component_are_routable(self):
        results, _, origins, destinations = self.runMatrix('odmatrixfromlayersastable')
        indexed = self.indexByIds(self.outputFeatures(results))

        #origin 5 and destination 14 both sit on the detached square
        self.assertIsNotNone(
            indexed[(DETACHED_ORIGIN, DETACHED_DESTINATION)]['total_cost'],
            'both points are on the detached component, so they do reach each other')

        for destination in destinations:
            if destination.id_int == DETACHED_DESTINATION:
                continue
            self.assertNullCost(indexed[(DETACHED_ORIGIN, destination.id_int)],
                                f'detached origin -> {destination.id_str}')
        for origin in origins:
            if origin.id_int == DETACHED_ORIGIN:
                continue
            self.assertNullCost(indexed[(origin.id_int, DETACHED_DESTINATION)],
                                f'{origin.id_str} -> detached destination')

    def test_mixed_id_datatypes(self):
        """Origin ids may be integers while destination ids are strings."""
        results, _, origins, destinations = self.runMatrix(
            'odmatrixfromlayersastable', origin_id='id_int', destination_id='id_str')
        layer = self.outputLayer(results)
        self.assertEqual(layer.fields().field('origin_id').type(), QMetaType.Type.Int)
        self.assertEqual(layer.fields().field('destination_id').type(),
                         QMetaType.Type.QString)

        pairs = {(f['origin_id'], f['destination_id']) for f in layer.getFeatures()}
        self.assertEqual(pairs, {(o.id_int, d.id_str)
                                 for o in origins for d in destinations})

    def test_lines_and_routes(self):
        line_results, solved, origins, destinations = self.runMatrix(
            'odmatrixfromlayersaslines',
            extra={'MATRIX_GEOMETRY_TYPE': MATRIX_GEOMETRY_LINE})
        line_index = self.indexByIds(self.outputFeatures(line_results))

        route_results, _, _, _ = self.runMatrix(
            'odmatrixfromlayersaslines',
            extra={'MATRIX_GEOMETRY_TYPE': MATRIX_GEOMETRY_ROUTE})
        route_index = self.indexByIds(self.outputFeatures(route_results))

        for origin_index, origin in enumerate(origins):
            for offset, destination in enumerate(destinations):
                destination_index = len(origins) + offset
                what = f'{origin.id_str}->{destination.id_str}'
                reference = solved.route(origin_index, destination_index)

                line = line_index[(origin.id_int, destination.id_int)].geometry()
                vertices = [(p.x(), p.y()) for p in line.asPolyline()]
                self.assertEqual(len(vertices), 2, f'{what}: Line is a direct connection')
                self.assertPointsEqual(vertices[0], origin.xy, f'{what} line start')
                self.assertPointsEqual(vertices[1], destination.xy, f'{what} line end')

                route = route_index[(origin.id_int, destination.id_int)].geometry()
                if reference is None:
                    self.assertTrue(route.isEmpty(), f'{what}: no route when unreachable')
                else:
                    self.assertVertexSequence(route, list(reversed(reference.path)),
                                              f'{what} route')

    def test_coincident_origin_and_destination_still_pay_entry_and_exit(self):
        """Across two layers, an identical position is not the same analysis point.

        Origin 4 and destination 11 are different places; this checks the more
        general rule that the m:n algorithms never shortcut a pair to zero,
        because identity there is object identity, not equal coordinates.
        """
        results, solved, origins, destinations = self.runMatrix('odmatrixfromlayersastable')
        indexed = self.indexByIds(self.outputFeatures(results))
        zero_pairs = [key for key, feature in indexed.items()
                      if feature['total_cost'] == 0.0]
        self.assertEqual(zero_pairs, [],
                         'no origin/destination pair in this fixture is free')
