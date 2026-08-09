# -*- coding: utf-8 -*-
"""
***************************************************************************
    test_shortest_path.py
    ---------------------

    qneat:shortestpathbetweenpoints

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

from . import fixtures
from .qneat_testcase import (QneatTestCase, STRATEGY_DISTANCE, STRATEGY_TIME)

ALGORITHM = 'shortestpathbetweenpoints'

EXPECTED_FIELDS = ['start_id', 'start_coordinates', 'start_entry_cost',
                   'end_id', 'end_coordinates', 'end_exit_cost',
                   'cost_on_graph', 'total_cost']


class ShortestPathTest(QneatTestCase):

    def route(self, start: tuple[float, float], end: tuple[float, float],
              strategy: int, epsg: int = fixtures.METRIC_EPSG):
        """Run the algorithm and return (feature, reference result)."""
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'START_POINT': f'{start[0]},{start[1]} [EPSG:{epsg}]',
            'END_POINT': f'{end[0]},{end[1]} [EPSG:{epsg}]',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        results = self.runAlgorithm(ALGORITHM, parameters)
        features = self.outputFeatures(results)
        self.assertEqual(len(features), 1, 'the algorithm returns exactly one path')

        reference = self.solve([start, end], strategy, epsg).route(0, 1)
        self.assertIsNotNone(reference, 'reference says this pair is unreachable')
        return features[0], reference, results

    def assertMatchesReference(self, feature, reference, strategy: int, what: str):
        self.assertCost(feature['start_entry_cost'], reference.entry_cost,
                        strategy, f'{what} entry')
        self.assertCost(feature['cost_on_graph'], reference.network_cost,
                        strategy, f'{what} network')
        self.assertCost(feature['end_exit_cost'], reference.exit_cost,
                        strategy, f'{what} exit')
        self.assertCost(feature['total_cost'], reference.total_cost,
                        strategy, f'{what} total')
        #QNEAT writes the route from the destination backwards
        self.assertVertexSequence(feature.geometry(),
                                  list(reversed(reference.path)), f'{what} geometry')

    # ------------------------------------------------------------------- schema

    def test_output_schema(self):
        origins = fixtures.origins()
        parameters = self.baseParameters()
        parameters.update({
            'START_POINT': '300000,62000 [EPSG:32118]',
            'END_POINT': '304000,62000 [EPSG:32118]',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        results = self.runAlgorithm(ALGORITHM, parameters)
        layer = self.outputLayer(results)

        self.assertFieldNames(layer, EXPECTED_FIELDS)
        self.assertEqual(layer.wkbType(), Qgis.WkbType.LineString)
        self.assertEqual(layer.crs().authid(), 'EPSG:32118')

        feature = next(layer.getFeatures())
        #the two points are synthesised with user ids 0 and 1, into string fields
        self.assertEqual(feature['start_id'], '0')
        self.assertEqual(feature['end_id'], '1')
        self.assertIn('300000', feature['start_coordinates'])
        self.assertTrue(origins, 'origin fixture is present')

    # ------------------------------------------------------- costs and geometry

    def test_distance_between_two_network_nodes(self):
        """c1r3 to c5r3, both exactly on nodes: no entry or exit cost at all."""
        feature, reference, _ = self.route((300000.0, 62000.0), (304000.0, 62000.0),
                                           STRATEGY_DISTANCE)
        self.assertMatchesReference(feature, reference, STRATEGY_DISTANCE, 'node to node')

        self.assertCost(feature['start_entry_cost'], 0.0, STRATEGY_DISTANCE, 'entry')
        self.assertCost(feature['end_exit_cost'], 0.0, STRATEGY_DISTANCE, 'exit')

        #the direct row 3 path is four edges; their stored lengths must add up to
        #the reported network cost, which pins the cost to the fixture itself
        stored = sum(fixtures.storedLength(fixtures.METRIC_EPSG, edge_id)
                     for edge_id in (9, 10, 11, 12))
        self.assertCost(feature['cost_on_graph'], stored, STRATEGY_DISTANCE,
                        'row 3 stored lengths')

    def test_time_takes_the_faster_detour(self):
        """Same pair by time: row 3 is 10 km/h, so the 100 km/h ring wins."""
        start, end = (300000.0, 62000.0), (304000.0, 62000.0)
        by_time, reference, _ = self.route(start, end, STRATEGY_TIME)
        self.assertMatchesReference(by_time, reference, STRATEGY_TIME, 'time')

        by_distance, _, _ = self.route(start, end, STRATEGY_DISTANCE)

        time_vertices = [(p.x(), p.y()) for p in by_time.geometry().asPolyline()]
        distance_vertices = [(p.x(), p.y()) for p in by_distance.geometry().asPolyline()]
        self.assertNotEqual(time_vertices, distance_vertices,
                            'time and distance optimisation must not pick the same route '
                            'here, or the fixture no longer discriminates between them')

        #the fast route drops to row 1 (y = 60000) and comes back up
        self.assertTrue(any(abs(y - 60000.0) < 1e-6 for _, y in time_vertices),
                        'fastest route should use the 100 km/h row 1 arterial')
        self.assertTrue(all(abs(y - 62000.0) < 1e-6 for _, y in distance_vertices),
                        'shortest route should stay on row 3')

        #and it must genuinely be faster than staying on row 3
        row3_metres = sum(fixtures.storedLength(fixtures.METRIC_EPSG, edge_id)
                          for edge_id in (9, 10, 11, 12))
        row3_seconds = row3_metres / (10.0 * 1000.0 / 3600.0)
        self.assertLess(by_time['cost_on_graph'], row3_seconds)

    def test_entry_and_exit_costs_off_network(self):
        """An origin off the network pays to reach it, measured ellipsoidally."""
        start = (299400.0, 59400.0)   # ties onto node c1r1
        end = (302000.0, 63000.0)     # sits on node c3r4
        feature, reference, _ = self.route(start, end, STRATEGY_DISTANCE)
        self.assertMatchesReference(feature, reference, STRATEGY_DISTANCE, 'off network')

        self.assertGreater(feature['start_entry_cost'], 0.0)
        self.assertCost(feature['end_exit_cost'], 0.0, STRATEGY_DISTANCE, 'exit')

        #entry cost is the ellipsoidal distance to the tie point, not the planar
        #one - on this CRS the two differ by about 2 mm over 850 m
        network = fixtures.referenceNetwork()
        snap = network.snap(start)
        self.assertPointsEqual(snap.point, (300000.0, 60000.0), 'tie point')
        planar = snap.planar_distance
        self.assertNotAlmostEqual(feature['start_entry_cost'], planar, places=4)
        self.assertCost(feature['start_entry_cost'],
                        network.projector.distance(start, snap.point),
                        STRATEGY_DISTANCE, 'ellipsoidal entry')

    def test_entry_cost_is_time_at_default_speed(self):
        """Optimising for time, the off graph leg is walked at the default speed."""
        start = (299400.0, 59400.0)
        end = (302000.0, 63000.0)
        feature, reference, _ = self.route(start, end, STRATEGY_TIME)
        self.assertMatchesReference(feature, reference, STRATEGY_TIME, 'off network by time')

        network = fixtures.referenceNetwork()
        metres = network.projector.distance(start, network.snap(start).point)
        self.assertCost(feature['start_entry_cost'], metres / (30.0 * 1000.0 / 3600.0),
                        STRATEGY_TIME, 'entry seconds at 30 km/h')

    def test_snapping_splits_an_edge(self):
        """A point nearest the middle of an edge ties there, not to a node."""
        start = (301500.0, 59400.0)   # 600 m below the middle of edge 2
        end = (304000.0, 62000.0)
        feature, reference, _ = self.route(start, end, STRATEGY_DISTANCE)
        self.assertMatchesReference(feature, reference, STRATEGY_DISTANCE, 'mid edge')

        vertices = [(p.x(), p.y()) for p in feature.geometry().asPolyline()]
        #route runs destination first, so the tie point is the second to last
        self.assertPointsEqual(vertices[-2], (301500.0, 60000.0), 'tie point on edge 2')
        self.assertGreater(feature['start_entry_cost'], 599.0)
        self.assertLess(feature['start_entry_cost'], 601.0)

    def test_points_sharing_one_tie_vertex(self):
        """Two points snapping to the same vertex cost nothing on the graph."""
        start = (299400.0, 59400.0)
        end = (299500.0, 59500.0)     # both nearest node c1r1
        network = fixtures.referenceNetwork()
        self.assertPointsEqual(network.snap(start).point, (300000.0, 60000.0), 'start tie')
        self.assertPointsEqual(network.snap(end).point, (300000.0, 60000.0), 'end tie')

        parameters = self.baseParameters()
        parameters.update({
            'START_POINT': f'{start[0]},{start[1]} [EPSG:32118]',
            'END_POINT': f'{end[0]},{end[1]} [EPSG:32118]',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        feature = self.outputFeatures(self.runAlgorithm(ALGORITHM, parameters))[0]

        self.assertCost(feature['cost_on_graph'], 0.0, STRATEGY_DISTANCE, 'network')
        entry = network.projector.distance(start, (300000.0, 60000.0))
        exit_cost = network.projector.distance(end, (300000.0, 60000.0))
        self.assertCost(feature['start_entry_cost'], entry, STRATEGY_DISTANCE, 'entry')
        self.assertCost(feature['end_exit_cost'], exit_cost, STRATEGY_DISTANCE, 'exit')
        self.assertCost(feature['total_cost'], entry + exit_cost,
                        STRATEGY_DISTANCE, 'total')
        self.assertFalse(feature.geometry().isEmpty())

    def test_unreachable_destination_raises(self):
        """The detached component cannot be routed to from the grid."""
        parameters = self.baseParameters()
        parameters.update({
            'START_POINT': '300000,62000 [EPSG:32118]',
            'END_POINT': '310500,70200 [EPSG:32118]',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        self.assertAlgorithmRaises(ALGORITHM, parameters, 'could not find a path')

        #and the reference agrees that there is no path
        solved = self.solve([(300000.0, 62000.0), (310500.0, 70200.0)], STRATEGY_DISTANCE)
        self.assertIsNone(solved.route(0, 1))

    def test_default_speed_applies_to_edge_without_speed(self):
        """Edge 25 has no speed value, so the time strategy falls back."""
        #c3r3 to c3r4 is edge 25, the one with an empty speed_kmh
        start, end = (302000.0, 62000.0), (302000.0, 63000.0)
        feature, reference, _ = self.route(start, end, STRATEGY_TIME)
        self.assertMatchesReference(feature, reference, STRATEGY_TIME, 'null speed edge')

        length = fixtures.storedLength(fixtures.METRIC_EPSG, 25)
        expected = length / (30.0 * 1000.0 / 3600.0)
        self.assertCost(feature['cost_on_graph'], expected, STRATEGY_TIME,
                        'edge 25 traversed at the default 30 km/h')
