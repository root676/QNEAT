# -*- coding: utf-8 -*-
"""
***************************************************************************
    test_iso_areas.py
    ---------------------

    qneat:isoareafrompoint    qneat:isoareafromlayer

    These produce two outputs at once: the cost surface raster, checked against
    a golden record, and the iso areas themselves. The iso areas come out of
    GDAL's contouring, so they are checked against the oracle by containment -
    a vertex the reference says is reachable within a cost level has to lie
    inside the polygon for that level.

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

from qgis.core import Qgis, QgsGeometry, QgsPointXY

from . import fixtures, raster_utils
from .qneat_testcase import (QneatTestCase, ISO_METHOD_EUCLIDEAN, ISO_METHOD_TIN,
                             ISO_TYPE_CONTOURS, ISO_TYPE_POLYGONS,
                             STRATEGY_DISTANCE, STRATEGY_TIME)

GOLDEN = 'iso_areas'

#c3r2, deliberately a central node: the TIN method interpolates over exactly
#the iso points' bounding box, so an origin at the edge of the network would put
#most of its own reachable vertices on the raster boundary, where contours
#cannot enclose them and the containment check has nothing left to assert
ORIGIN_CENTRAL = (302000.0, 61000.0)
CELL_SIZE = 100.0
MAX_COST = 2000.0
INTERVAL = 500.0

EXPECTED_FIELDS = ['id', 'cost_level']

#a vertex this far below a cost level must be safely inside that level's
#polygon; closer than this and raster discretisation can legitimately put it on
#the wrong side of the contour
CONTAINMENT_MARGIN = 2.0 * CELL_SIZE


def expectedLevels(max_cost: float, interval: float) -> list[float]:
    """The levels QNEAT contours at.

    It inflates max_cost by 10% first, so that the last requested band is drawn
    completely rather than clipped at its own boundary.
    """
    inflated = max_cost * 1.1
    return [index * interval for index in range(int(inflated / interval) + 1)]


class IsoAreaTestBase(QneatTestCase):

    def assertLevelsAreSane(self, features, max_cost, interval, what):
        levels = sorted({feature['cost_level'] for feature in features})
        allowed = expectedLevels(max_cost, interval)
        for level in levels:
            self.assertIn(level, allowed, f'{what}: unexpected cost level {level}')
        self.assertGreaterEqual(len(levels), 2,
                                f'{what}: expected several bands, got {levels}')
        return levels

    def assertReachableVerticesAreInside(self, features, solved, origin_indices,
                                         strategy, what, surface_path):
        """The oracle's reachable vertices must fall inside the matching band.

        Vertices within one cell of the raster boundary are left out. Contours
        are traced between cell centres, so the outermost half cell of the cost
        surface can never be enclosed by a polygon - and the TIN method uses the
        iso points' own bounding box as its extent, which puts the outermost
        vertices exactly there. That is discretisation at the edge of the grid,
        not a misplaced iso area.
        """
        summary = raster_utils.summarise(surface_path)
        left, pixel_x, _, top, _, pixel_y = summary.geotransform
        right = left + summary.width * pixel_x
        bottom = top + summary.height * pixel_y
        inset = abs(pixel_x)

        by_level = {}
        for feature in features:
            by_level.setdefault(feature['cost_level'], []).append(feature.geometry())

        margin = CONTAINMENT_MARGIN
        if strategy == STRATEGY_TIME:
            margin = CONTAINMENT_MARGIN / (30.0 * 1000.0 / 3600.0)

        checked = 0
        for level, geometries in by_level.items():
            if level <= 0.0:
                continue
            reachable = solved.isoPoints(origin_indices, level - margin)
            for (x, y), _ in reachable.items():
                if not (left + inset < x < right - inset
                        and bottom + inset < y < top - inset):
                    continue
                point = QgsGeometry.fromPointXY(QgsPointXY(x, y))
                inside = any(geometry.contains(point) for geometry in geometries)
                self.assertTrue(
                    inside,
                    f'{what}: vertex ({x}, {y}) is reachable well within '
                    f'cost level {level}, but lies outside that iso area')
                checked += 1
        self.assertGreater(checked, 5, f'{what}: too few vertices actually checked')

    def assertBandsAreNested(self, features, what):
        """Each polygon band must contain every cheaper one."""
        polygons = sorted(((f['cost_level'], f.geometry()) for f in features),
                          key=lambda item: item[0])
        for (inner_level, inner), (outer_level, outer) in zip(polygons, polygons[1:]):
            self.assertLessEqual(
                inner.area(), outer.area() + 1e-6,
                f'{what}: band {outer_level} is smaller than band {inner_level}')
            #buffered by a cell, because both boundaries are traced on the same
            #raster grid and can share a cell edge
            self.assertTrue(
                outer.buffer(CELL_SIZE, 8).contains(inner),
                f'{what}: band {inner_level} is not enclosed by band {outer_level}')


class IsoAreaFromPointTest(IsoAreaTestBase):

    def runIsoArea(self, iso_type, method=ISO_METHOD_EUCLIDEAN,
                   strategy=STRATEGY_DISTANCE, origin=ORIGIN_CENTRAL,
                   max_cost=MAX_COST, interval=INTERVAL, epsg=fixtures.METRIC_EPSG):
        surface = self.outputPath('iso_surface')
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'ORIGIN_POINT': f'{origin[0]},{origin[1]} [EPSG:{epsg}]',
            'ISO_AREA_METHOD': method,
            'ISO_AREA_TYPE': iso_type,
            'MAX_COST': max_cost,
            'INTERVAL': interval,
            'CELL_SIZE': CELL_SIZE,
            'MAX_OFF_GRAPH_TRAVEL_COST': 0.0,
            'OUTPUT_COST_SURFACE': surface,
            'OUTPUT_ISO_AREAS': 'TEMPORARY_OUTPUT',
        })
        results = self.runAlgorithm('isoareafrompoint', parameters)
        return results, surface, self.solve([origin], strategy, epsg)

    def test_polygon_output(self):
        results, surface, solved = self.runIsoArea(ISO_TYPE_POLYGONS)
        layer = self.outputLayer(results, 'OUTPUT_ISO_AREAS')

        self.assertFieldNames(layer, EXPECTED_FIELDS)
        self.assertEqual(layer.wkbType(), Qgis.WkbType.MultiPolygon)
        self.assertEqual(layer.crs().authid(), 'EPSG:32118')

        features = list(layer.getFeatures())
        levels = self.assertLevelsAreSane(features, MAX_COST, INTERVAL, 'polygons')

        for feature in features:
            self.assertFalse(feature.geometry().isEmpty())
            self.assertGreater(feature.geometry().area(), 0.0)

        self.assertBandsAreNested(features, 'polygons')
        self.assertReachableVerticesAreInside(features, solved, [0],
                                              STRATEGY_DISTANCE, 'polygons', surface)

        #and the accompanying cost surface is the usual raster
        self.assertRasterMatchesGolden(surface, GOLDEN, 'polygons_surface')
        self.assertIn(500.0, levels)

    def test_polygons_are_written_largest_first(self):
        """Bands come out in descending cost order so the small ones stay visible."""
        results, _, _ = self.runIsoArea(ISO_TYPE_POLYGONS)
        levels = [f['cost_level'] for f in self.outputFeatures(results, 'OUTPUT_ISO_AREAS')]
        self.assertEqual(levels, sorted(levels, reverse=True))

    def test_contour_output(self):
        results, surface, solved = self.runIsoArea(ISO_TYPE_CONTOURS)
        layer = self.outputLayer(results, 'OUTPUT_ISO_AREAS')

        self.assertFieldNames(layer, EXPECTED_FIELDS)
        self.assertEqual(layer.wkbType(), Qgis.WkbType.MultiLineString)

        features = list(layer.getFeatures())
        self.assertLevelsAreSane(features, MAX_COST, INTERVAL, 'contours')
        for feature in features:
            self.assertFalse(feature.geometry().isEmpty())
            self.assertGreater(feature.geometry().length(), 0.0,
                               'a contour with no length is not a contour')
            #lines, unlike the polygon bands, enclose no area
            self.assertAlmostEqual(feature.geometry().area(), 0.0, places=6)

        self.assertRasterMatchesGolden(surface, GOLDEN, 'contours_surface')

    def test_polygons_and_contours_describe_the_same_levels(self):
        polygons, _, _ = self.runIsoArea(ISO_TYPE_POLYGONS)
        contours, _, _ = self.runIsoArea(ISO_TYPE_CONTOURS)

        polygon_levels = {f['cost_level']
                          for f in self.outputFeatures(polygons, 'OUTPUT_ISO_AREAS')}
        contour_levels = {f['cost_level']
                          for f in self.outputFeatures(contours, 'OUTPUT_ISO_AREAS')}
        self.assertEqual(polygon_levels, contour_levels)

    def test_time_iso_areas(self):
        results, surface, solved = self.runIsoArea(ISO_TYPE_POLYGONS,
                                                   strategy=STRATEGY_TIME,
                                                   max_cost=400.0, interval=100.0)
        features = self.outputFeatures(results, 'OUTPUT_ISO_AREAS')
        self.assertLevelsAreSane(features, 400.0, 100.0, 'time polygons')
        self.assertBandsAreNested(features, 'time polygons')
        self.assertReachableVerticesAreInside(features, solved, [0],
                                              STRATEGY_TIME, 'time polygons', surface)
        self.assertRasterMatchesGolden(surface, GOLDEN, 'time_polygons_surface')

    def test_tin_iso_areas(self):
        results, surface, solved = self.runIsoArea(ISO_TYPE_POLYGONS,
                                                   method=ISO_METHOD_TIN)
        features = self.outputFeatures(results, 'OUTPUT_ISO_AREAS')
        self.assertLevelsAreSane(features, MAX_COST, INTERVAL, 'tin polygons')
        self.assertReachableVerticesAreInside(features, solved, [0],
                                              STRATEGY_DISTANCE, 'tin polygons', surface)
        self.assertRasterMatchesGolden(surface, GOLDEN, 'tin_polygons_surface')

    def test_a_wider_budget_grows_the_areas(self):
        small, _, _ = self.runIsoArea(ISO_TYPE_POLYGONS, max_cost=1000.0)
        large, _, _ = self.runIsoArea(ISO_TYPE_POLYGONS, max_cost=2000.0)

        def widest(results):
            features = self.outputFeatures(results, 'OUTPUT_ISO_AREAS')
            return max(f.geometry().area() for f in features)

        self.assertGreater(widest(large), widest(small),
                           'doubling the budget must enlarge the iso area')


class IsoAreaFromLayerTest(IsoAreaTestBase):

    def runIsoArea(self, iso_type, keep, method=ISO_METHOD_EUCLIDEAN,
                   strategy=STRATEGY_DISTANCE, id_field='id_int',
                   max_cost=MAX_COST, interval=INTERVAL, epsg=fixtures.METRIC_EPSG):
        surface = self.outputPath('iso_surface_layer')
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'ORIGIN_POINT_LAYER': self.pointLayer('origins', epsg, keep=keep),
            'ORIGIN_ID_FIELD': id_field,
            'ISO_AREA_METHOD': method,
            'ISO_AREA_TYPE': iso_type,
            'MAX_COST': max_cost,
            'INTERVAL': interval,
            'CELL_SIZE': CELL_SIZE,
            'MAX_OFF_GRAPH_TRAVEL_COST': 0.0,
            'OUTPUT_COST_SURFACE': surface,
            'OUTPUT_ISO_AREAS': 'TEMPORARY_OUTPUT',
        })
        results = self.runAlgorithm('isoareafromlayer', parameters)

        points = [p for p in fixtures.origins(epsg) if p.id_int in keep]
        return results, surface, self.solve([p.xy for p in points], strategy, epsg)

    def test_polygons_from_two_origins(self):
        results, surface, solved = self.runIsoArea(ISO_TYPE_POLYGONS, keep=[1, 4])
        layer = self.outputLayer(results, 'OUTPUT_ISO_AREAS')

        self.assertFieldNames(layer, EXPECTED_FIELDS)
        self.assertEqual(layer.wkbType(), Qgis.WkbType.MultiPolygon)

        features = list(layer.getFeatures())
        self.assertLevelsAreSane(features, MAX_COST, INTERVAL, 'two origin polygons')
        self.assertBandsAreNested(features, 'two origin polygons')
        self.assertReachableVerticesAreInside(features, solved, [0, 1],
                                              STRATEGY_DISTANCE, 'two origin polygons', surface)
        self.assertRasterMatchesGolden(surface, GOLDEN, 'layer_polygons_surface')

    def test_contours_from_two_origins(self):
        results, surface, _ = self.runIsoArea(ISO_TYPE_CONTOURS, keep=[1, 4])
        layer = self.outputLayer(results, 'OUTPUT_ISO_AREAS')
        self.assertEqual(layer.wkbType(), Qgis.WkbType.MultiLineString)
        self.assertLevelsAreSane(list(layer.getFeatures()), MAX_COST, INTERVAL,
                                 'two origin contours')
        self.assertRasterMatchesGolden(surface, GOLDEN, 'layer_contours_surface')

    def test_string_id_field_is_accepted(self):
        """The id field's datatype is threaded into the iso point attributes."""
        results, _, _ = self.runIsoArea(ISO_TYPE_POLYGONS, keep=[1, 4],
                                        id_field='id_str')
        features = self.outputFeatures(results, 'OUTPUT_ISO_AREAS')
        self.assertGreater(len(features), 0)
