# -*- coding: utf-8 -*-
"""
***************************************************************************
    test_iso_cost_surface.py
    ---------------------

    qneat:isoareaascostsurfacefrompoint    qneat:isoareaascostsurfacefromlayer

    Raster outputs, checked as hash plus structure plus probed pixels - see
    tests/raster_utils.py for why all three.

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
from .qneat_testcase import (QneatTestCase, DEFAULT_SPEED,
                             ISO_METHOD_EUCLIDEAN, ISO_METHOD_TIN,
                             STRATEGY_DISTANCE, STRATEGY_TIME)

GOLDEN = 'cost_surface'

ORIGIN_ON_NODE = (300000.0, 62000.0)
CELL_SIZE = 100.0

#a probed pixel is the value at the centre of the cell containing the vertex,
#and the seeds themselves are only laid down every cell_size * 1.5 along the
#edges, so the value can legitimately be off by a couple of cells' worth of
#cost. Wide enough to absorb that, far too tight to hide a unit error.
DISTANCE_PIXEL_DELTA = 2.5 * CELL_SIZE
TIME_PIXEL_DELTA = DISTANCE_PIXEL_DELTA / (DEFAULT_SPEED * 1000.0 / 3600.0)


class CostSurfaceTestBase(QneatTestCase):

    def assertVerticesAreOnTheSurface(self, path, solved, origin_indices, max_cost,
                                      strategy, what):
        """Every reachable vertex must read back roughly its own cost."""
        delta = DISTANCE_PIXEL_DELTA if strategy == STRATEGY_DISTANCE else TIME_PIXEL_DELTA
        probed = 0
        for (x, y), (cost, _) in solved.isoPoints(origin_indices, max_cost).items():
            value = raster_utils.sample(path, x, y)
            if value is None:
                #vertices right on the edge of the interpolation extent can fall
                #outside the last cell; those are not what this check is about
                continue
            self.assertAlmostEqual(
                value, cost, delta=delta,
                msg=f'{what}: cell at ({x}, {y}) reads {value}, '
                    f'but the vertex there costs {cost}')
            probed += 1
        self.assertGreater(probed, 5, f'{what}: too few vertices actually probed')


class CostSurfaceFromPointTest(CostSurfaceTestBase):

    def runSurface(self, max_cost, method, strategy=STRATEGY_DISTANCE,
                   origin=ORIGIN_ON_NODE, cap=0.0, epsg=fixtures.METRIC_EPSG):
        output = self.outputPath('cost_surface')
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'ORIGIN_POINT': f'{origin[0]},{origin[1]} [EPSG:{epsg}]',
            'MAX_COST': max_cost,
            'ISO_AREA_METHOD': method,
            'CELL_SIZE': CELL_SIZE,
            'MAX_OFF_GRAPH_TRAVEL_COST': cap,
            'OUTPUT': output,
        })
        self.runAlgorithm('isoareaascostsurfacefrompoint', parameters)
        return output, self.solve([origin], strategy, epsg)

    # ---------------------------------------------------------------- euclidean

    def test_euclidean_distance_surface(self):
        path, solved = self.runSurface(2500.0, ISO_METHOD_EUCLIDEAN)
        summary = self.assertRasterMatchesGolden(path, GOLDEN, 'euclidean_distance')

        self.assertEqual(summary.bands, 1)
        self.assertEqual(summary.data_type, 'Float32')
        self.assertEqual(summary.nodata, -9999.0)
        self.assertEqual(summary.authid, 'EPSG:32118')
        #square cells, north up
        self.assertAlmostEqual(summary.geotransform[1], CELL_SIZE, places=6)
        self.assertAlmostEqual(summary.geotransform[5], -CELL_SIZE, places=6)
        self.assertEqual(summary.geotransform[2], 0.0)
        self.assertEqual(summary.geotransform[4], 0.0)
        self.assertGreaterEqual(summary.minimum, 0.0)

        self.assertVerticesAreOnTheSurface(path, solved, [0], 2500.0,
                                           STRATEGY_DISTANCE, 'euclidean distance')

        #the origin sits on the network, so it costs nothing to be there
        self.assertRasterSample(path, ORIGIN_ON_NODE, 0.0, DISTANCE_PIXEL_DELTA,
                                'origin cell')

    def test_euclidean_time_surface(self):
        path, solved = self.runSurface(400.0, ISO_METHOD_EUCLIDEAN,
                                       strategy=STRATEGY_TIME)
        summary = self.assertRasterMatchesGolden(path, GOLDEN, 'euclidean_time')
        self.assertEqual(summary.authid, 'EPSG:32118')

        self.assertVerticesAreOnTheSurface(path, solved, [0], 400.0,
                                           STRATEGY_TIME, 'euclidean time')

        #seconds, not metres: the whole surface has to stay inside the budget
        #plus the off graph travel the raster adds around the seeds
        self.assertLess(summary.maximum, 400.0 + TIME_PIXEL_DELTA * 20.0,
                        'time surface values look like metres, not seconds')

    def test_off_graph_travel_cap_masks_distant_cells(self):
        """Capping off graph travel turns far cells into nodata, nothing else."""
        uncapped, _ = self.runSurface(2500.0, ISO_METHOD_EUCLIDEAN)
        capped, solved = self.runSurface(2500.0, ISO_METHOD_EUCLIDEAN, cap=200.0)

        uncapped_summary = raster_utils.summarise(uncapped)
        capped_summary = self.assertRasterMatchesGolden(capped, GOLDEN,
                                                        'euclidean_distance_capped')

        self.assertEqual(capped_summary.width, uncapped_summary.width)
        self.assertEqual(capped_summary.height, uncapped_summary.height)
        self.assertLess(capped_summary.valid_count, uncapped_summary.valid_count,
                        'a 200 m cap must remove cells from the surface')

        #cells on the network survive the cap
        self.assertVerticesAreOnTheSurface(capped, solved, [0], 2500.0,
                                           STRATEGY_DISTANCE, 'capped')

        #and a cell well beyond the cap, inside the raster but away from any
        #edge, is masked out
        far = (300500.0, 60500.0)   # middle of a grid cell, 500 m from any edge
        self.assertIsNotNone(raster_utils.sample(uncapped, *far),
                             'the uncapped surface should cover the grid interior')
        self.assertIsNone(raster_utils.sample(capped, *far),
                          'the capped surface must not reach the middle of a block')

    # --------------------------------------------------------------------- TIN

    def test_tin_distance_surface(self):
        path, solved = self.runSurface(2500.0, ISO_METHOD_TIN)
        summary = self.assertRasterMatchesGolden(path, GOLDEN, 'tin_distance')

        self.assertEqual(summary.bands, 1)
        self.assertAlmostEqual(abs(summary.geotransform[1]), CELL_SIZE, delta=CELL_SIZE)
        self.assertVerticesAreOnTheSurface(path, solved, [0], 2500.0,
                                           STRATEGY_DISTANCE, 'tin distance')

    def test_tin_time_surface(self):
        path, solved = self.runSurface(400.0, ISO_METHOD_TIN, strategy=STRATEGY_TIME)
        self.assertRasterMatchesGolden(path, GOLDEN, 'tin_time')
        self.assertVerticesAreOnTheSurface(path, solved, [0], 400.0,
                                           STRATEGY_TIME, 'tin time')

    def test_the_two_methods_disagree(self):
        """Euclidean allocation and TIN interpolation are genuinely different.

        If these ever produced the same raster, the method parameter would not
        be doing anything and the golden files would be testing one code path.
        """
        euclidean, _ = self.runSurface(2500.0, ISO_METHOD_EUCLIDEAN)
        tin, _ = self.runSurface(2500.0, ISO_METHOD_TIN)
        self.assertNotEqual(raster_utils.summarise(euclidean).digest,
                            raster_utils.summarise(tin).digest)


class CostSurfaceFromLayerTest(CostSurfaceTestBase):

    def runSurface(self, max_cost, method, keep, strategy=STRATEGY_DISTANCE,
                   id_field='id_int', epsg=fixtures.METRIC_EPSG):
        output = self.outputPath('cost_surface_layer')
        parameters = self.baseParameters(epsg, strategy)
        parameters.update({
            'ORIGIN_POINTS': self.pointLayer('origins', epsg, keep=keep),
            'ORIGIN_ID_FIELD': id_field,
            'MAX_COST': max_cost,
            'ISO_AREA_METHOD': method,
            'CELL_SIZE': CELL_SIZE,
            'MAX_OFF_GRAPH_TRAVEL_COST': 0.0,
            'OUTPUT': output,
        })
        self.runAlgorithm('isoareaascostsurfacefromlayer', parameters)

        points = [p for p in fixtures.origins(epsg) if p.id_int in keep]
        return output, self.solve([p.xy for p in points], strategy, epsg)

    def test_euclidean_from_two_origins(self):
        path, solved = self.runSurface(2000.0, ISO_METHOD_EUCLIDEAN, keep=[1, 4])
        summary = self.assertRasterMatchesGolden(path, GOLDEN, 'layer_euclidean_distance')
        self.assertEqual(summary.authid, 'EPSG:32118')
        self.assertEqual(summary.nodata, -9999.0)
        self.assertVerticesAreOnTheSurface(path, solved, [0, 1], 2000.0,
                                           STRATEGY_DISTANCE, 'two origins')

        #both origins are network nodes, so both read as free
        for origin in (1, 4):
            point = [p for p in fixtures.origins() if p.id_int == origin][0]
            self.assertRasterSample(path, point.xy, 0.0, DISTANCE_PIXEL_DELTA,
                                    f'origin {origin} cell')

    def test_tin_from_two_origins(self):
        path, solved = self.runSurface(2000.0, ISO_METHOD_TIN, keep=[1, 4])
        self.assertRasterMatchesGolden(path, GOLDEN, 'layer_tin_distance')
        self.assertVerticesAreOnTheSurface(path, solved, [0, 1], 2000.0,
                                           STRATEGY_DISTANCE, 'two origins tin')

    def test_more_origins_cover_more_ground(self):
        one, _ = self.runSurface(2000.0, ISO_METHOD_EUCLIDEAN, keep=[1])
        two, _ = self.runSurface(2000.0, ISO_METHOD_EUCLIDEAN, keep=[1, 4])
        self.assertGreater(raster_utils.summarise(two).valid_count,
                           raster_utils.summarise(one).valid_count,
                           'adding an origin at the far end must extend the surface')
