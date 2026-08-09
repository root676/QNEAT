# -*- coding: utf-8 -*-
"""
***************************************************************************
    test_crs_parity.py
    ---------------------

    The same network, the same points, two coordinate reference systems.

    EPSG:32118 and EPSG:2263 are the same Lambert Conformal Conic 2SP
    projection on the same NAD83/GRS80 datum and differ only in linear unit -
    metres against US survey feet. The fixtures are exact unit conversions of
    one another, so they describe the very same places on the ellipsoid.

    QNEAT costs are always ellipsoidal: real metres for the distance strategy
    and real seconds for the time strategy, never map units. Both CRSs must
    therefore return identical numbers. Anything that reads a map unit and
    forgets to convert it - entry costs, the speed factor, the proximity raster -
    shows up here as a factor of 3.28 and nowhere else.

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

from . import fixtures, raster_utils
from .oracle import nodeKey
from .qneat_testcase import (QneatTestCase, ISO_METHOD_EUCLIDEAN, ISO_METHOD_TIN,
                             METRE_TOLERANCE, SECOND_TOLERANCE,
                             STRATEGY_DISTANCE, STRATEGY_TIME)

METRIC = fixtures.METRIC_EPSG
FOOT = fixtures.FOOT_EPSG

#exact, by definition of the US survey foot
FEET_PER_METRE = 3937.0 / 1200.0

CELL_SIZE_METRES = 100.0
CELL_SIZE_FEET = CELL_SIZE_METRES * FEET_PER_METRE

#the foot fixtures are written with four decimals, which is 0.03 mm, and the
#projection round trip adds a little more - so parity is asserted a shade looser
#than the single CRS tests, while still being far below any real error
PARITY_METRE_TOLERANCE = 10.0 * METRE_TOLERANCE
PARITY_SECOND_TOLERANCE = 10.0 * SECOND_TOLERANCE


#the foot fixtures are written with four decimals of a foot, which is 0.03 mm
FIXTURE_DECIMALS = 4


def toFeet(xy: tuple[float, float]) -> tuple[float, float]:
    """Convert to feet and onto the fixture's own coordinate grid.

    The rounding matters. A converted point carrying full float precision misses
    the network node it is meant to sit on by a few hundredths of a millimetre,
    and with a topology tolerance of zero the director then ties it onto the
    edge just beside the node and splits it. The costs come out the same to
    within that fraction of a millimetre, but the graph gains a vertex that the
    metric run does not have, which is a difference in the fixture, not in QNEAT.
    """
    return (round(xy[0] * FEET_PER_METRE, FIXTURE_DECIMALS),
            round(xy[1] * FEET_PER_METRE, FIXTURE_DECIMALS))


class CrsParityTest(QneatTestCase):

    def tolerance(self, strategy: int) -> float:
        return (PARITY_METRE_TOLERANCE if strategy == STRATEGY_DISTANCE
                else PARITY_SECOND_TOLERANCE)

    def assertParity(self, metric_value, foot_value, strategy, what):
        if metric_value is None or foot_value is None:
            self.assertEqual(metric_value, foot_value,
                             f'{what}: reachability differs between the two CRSs')
            return
        self.assertAlmostEqual(float(foot_value), float(metric_value),
                               delta=self.tolerance(strategy),
                               msg=f'{what}: costs differ between EPSG:{METRIC} '
                                   f'and EPSG:{FOOT}')

    # ------------------------------------------------------- fixtures agreement

    def test_the_two_fixtures_describe_the_same_network(self):
        """Guard on the fixtures themselves, before anything is asserted with them."""
        metric = fixtures.referenceNetwork(METRIC)
        feet = fixtures.referenceNetwork(FOOT)
        self.assertEqual(len(metric.edges), len(feet.edges))

        for index, (metric_edge, foot_edge) in enumerate(zip(metric.edges, feet.edges)):
            self.assertEqual(metric_edge.speed_kmh, foot_edge.speed_kmh,
                             f'edge {index}: speeds differ')
            #the geodesic length of an edge does not care what unit it is drawn in
            self.assertAlmostEqual(feet.edgeLength(index), metric.edgeLength(index),
                                   delta=PARITY_METRE_TOLERANCE,
                                   msg=f'edge {index}: geodesic length differs')

    # ------------------------------------------------------------ shortest path

    def runShortestPath(self, start, end, strategy, epsg):
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'START_POINT': f'{start[0]},{start[1]} [EPSG:{epsg}]',
            'END_POINT': f'{end[0]},{end[1]} [EPSG:{epsg}]',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        return self.outputFeatures(self.runAlgorithm('shortestpathbetweenpoints',
                                                     parameters))[0]

    def test_shortest_path_costs_match(self):
        #an off network start, so the entry cost is exercised as well
        start = (299400.0, 59400.0)
        end = (304000.0, 62000.0)

        for strategy in (STRATEGY_DISTANCE, STRATEGY_TIME):
            metric = self.runShortestPath(start, end, strategy, METRIC)
            feet = self.runShortestPath(toFeet(start), toFeet(end), strategy, FOOT)

            for field in ('start_entry_cost', 'cost_on_graph',
                          'end_exit_cost', 'total_cost'):
                self.assertParity(metric[field], feet[field], strategy,
                                  f'shortest path {field} (strategy {strategy})')

            #the routes are the same places, just drawn in different units
            metric_vertices = [(p.x(), p.y())
                               for p in metric.geometry().asPolyline()]
            foot_vertices = [(p.x(), p.y()) for p in feet.geometry().asPolyline()]
            self.assertEqual(len(metric_vertices), len(foot_vertices),
                             'the two CRSs picked different routes')
            for index, (metric_point, foot_point) in enumerate(
                    zip(metric_vertices, foot_vertices)):
                expected = toFeet(metric_point)
                self.assertAlmostEqual(foot_point[0], expected[0], delta=0.01,
                                       msg=f'route vertex {index} x')
                self.assertAlmostEqual(foot_point[1], expected[1], delta=0.01,
                                       msg=f'route vertex {index} y')

    # ------------------------------------------------------------- od matrix

    def runMatrix(self, strategy, epsg):
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'POINTS': self.pointLayer('origins', epsg),
            'ID_FIELD': 'id_int',
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        features = self.outputFeatures(
            self.runAlgorithm('odmatrixfrompointsastable', parameters))
        return {(f['origin_id'], f['destination_id']): f for f in features}

    def test_od_matrix_costs_match(self):
        for strategy in (STRATEGY_DISTANCE, STRATEGY_TIME):
            metric = self.runMatrix(strategy, METRIC)
            feet = self.runMatrix(strategy, FOOT)
            self.assertEqual(sorted(metric), sorted(feet),
                             'the two CRSs produced different od pairs')

            for key in metric:
                for field in ('entry_cost', 'network_cost', 'exit_cost', 'total_cost'):
                    self.assertParity(metric[key][field], feet[key][field], strategy,
                                      f'od pair {key} {field} (strategy {strategy})')

    # ------------------------------------------------------------- pointcloud

    def runPointcloud(self, max_cost, strategy, epsg, origin):
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'ORIGIN_POINT': f'{origin[0]},{origin[1]} [EPSG:{epsg}]',
            'MAX_COST': max_cost,
            'OUTPUT': 'TEMPORARY_OUTPUT',
        })
        features = self.outputFeatures(
            self.runAlgorithm('isoareaaspointcloudfrompoint', parameters))
        return {nodeKey((f.geometry().constGet().x(), f.geometry().constGet().y())): f
                for f in features}

    def test_pointcloud_costs_match(self):
        origin = (302000.0, 61000.0)
        metric = self.runPointcloud(2100.0, STRATEGY_DISTANCE, METRIC, origin)
        feet = self.runPointcloud(2100.0, STRATEGY_DISTANCE, FOOT, toFeet(origin))

        self.assertEqual(len(metric), len(feet),
                         'the same cost budget must reach the same number of vertices')

        for key, feature in metric.items():
            match = feet.get(nodeKey(toFeet(key)))
            self.assertIsNotNone(match, f'vertex {key} is missing from the foot run')
            self.assertParity(feature['cost'], match['cost'], STRATEGY_DISTANCE,
                              f'pointcloud vertex {key}')

    # ----------------------------------------------------------- cost surface

    def runCostSurface(self, method, strategy, epsg, origin, cell_size, max_cost):
        output = self.outputPath('parity_surface')
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'ORIGIN_POINT': f'{origin[0]},{origin[1]} [EPSG:{epsg}]',
            'MAX_COST': max_cost,
            'ISO_AREA_METHOD': method,
            'CELL_SIZE': cell_size,
            'MAX_OFF_GRAPH_TRAVEL_COST': 0.0,
            'OUTPUT': output,
        })
        self.runAlgorithm('isoareaascostsurfacefrompoint', parameters)
        return output

    def assertSurfaceParity(self, method, strategy, max_cost, what):
        origin = (302000.0, 61000.0)
        metric = self.runCostSurface(method, strategy, METRIC, origin,
                                     CELL_SIZE_METRES, max_cost)
        feet = self.runCostSurface(method, strategy, FOOT, toFeet(origin),
                                   CELL_SIZE_FEET, max_cost)

        metric_summary = raster_utils.summarise(metric)
        foot_summary = raster_utils.summarise(feet)

        #same grid, just measured differently
        self.assertEqual((foot_summary.width, foot_summary.height),
                         (metric_summary.width, metric_summary.height),
                         f'{what}: the two CRSs produced differently shaped rasters')

        #the values are costs, so they must not be converted at all
        compared = 0
        for row in range(2, metric_summary.height - 2, 3):
            for column in range(2, metric_summary.width - 2, 3):
                x = metric_summary.geotransform[0] + (column + 0.5) * CELL_SIZE_METRES
                y = metric_summary.geotransform[3] - (row + 0.5) * CELL_SIZE_METRES
                metric_value = raster_utils.sample(metric, x, y)
                foot_value = raster_utils.sample(feet, *toFeet((x, y)))
                if metric_value is None or foot_value is None:
                    continue
                #a shade looser than the vector parity: the two grids are laid
                #out independently, so a probe can land in cells whose centres
                #are up to half a cell apart
                self.assertAlmostEqual(
                    foot_value, metric_value,
                    delta=0.05 * max(1.0, abs(metric_value)) + 1.0,
                    msg=f'{what}: cell at ({x:.0f}, {y:.0f}) reads {metric_value} '
                        f'in metres and {foot_value} in feet')
                compared += 1
        self.assertGreater(compared, 20, f'{what}: too few cells compared')

    def test_euclidean_cost_surface_values_match(self):
        self.assertSurfaceParity(ISO_METHOD_EUCLIDEAN, STRATEGY_DISTANCE, 2000.0,
                                 'euclidean distance surface')

    def test_euclidean_time_cost_surface_values_match(self):
        self.assertSurfaceParity(ISO_METHOD_EUCLIDEAN, STRATEGY_TIME, 400.0,
                                 'euclidean time surface')

    def test_tin_cost_surface_values_match(self):
        self.assertSurfaceParity(ISO_METHOD_TIN, STRATEGY_DISTANCE, 2000.0,
                                 'tin distance surface')
