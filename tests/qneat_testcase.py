# -*- coding: utf-8 -*-
"""
***************************************************************************
    qneat_testcase.py
    ---------------------

    Base class for the QNEAT algorithm tests: starts QGIS, runs processing
    algorithms and provides the assertions the individual test modules use.

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

import math
import os
import shutil
import tempfile
import unittest

from typing import Optional

from . import qgis_bootstrap

qgis_bootstrap.start()

from qgis.core import (QgsFeature,  # noqa: E402
                       QgsProcessingContext,
                       QgsProcessingException,
                       QgsProcessingFeedback,
                       QgsProcessingUtils,
                       QgsProject)

import processing  # noqa: E402

from . import fixtures  # noqa: E402
from . import raster_utils  # noqa: E402
from .oracle import DISTANCE, TIME  # noqa: E402

#Vincenty here against QgsDistanceArea's own ellipsoidal formula in C++ agree
#far below a millimetre per edge, so a millimetre over a whole route is a
#generous ceiling that still catches any real error.
METRE_TOLERANCE = 1e-3
#the slowest network speed is 10 km/h, so a millimetre is well under a
#millisecond - a millisecond is again generous
SECOND_TOLERANCE = 1e-3

#tie points and route vertices should reproduce exactly; this only absorbs
#float noise in the projection round trip
COORDINATE_TOLERANCE = 1e-4

#off graph travel speed used throughout, in km/h. Explicit rather than relying
#on the parameter default, because the oracle has to use the same number.
DEFAULT_SPEED = 30.0

STRATEGY_DISTANCE = 0
STRATEGY_TIME = 1

ISO_METHOD_EUCLIDEAN = 0
ISO_METHOD_TIN = 1

ISO_TYPE_POLYGONS = 0
ISO_TYPE_CONTOURS = 1

MATRIX_GEOMETRY_LINE = 0
MATRIX_GEOMETRY_ROUTE = 1

STRATEGY_NAMES = {STRATEGY_DISTANCE: DISTANCE, STRATEGY_TIME: TIME}


class CollectingFeedback(QgsProcessingFeedback):
    """Keeps whatever an algorithm reports, so a failure can say what went wrong."""

    def __init__(self):
        super().__init__(False)
        self.errors: list[str] = []
        self.messages: list[str] = []

    def reportError(self, error: str, fatalError: bool = False):
        self.errors.append(error)

    def pushInfo(self, info: str):
        self.messages.append(info)

    def pushWarning(self, warning: str):
        self.messages.append(warning)


class QneatTestCase(unittest.TestCase):
    """Shared machinery for every QNEAT algorithm test."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.provider = qgis_bootstrap.start()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix='qneat_test_')
        self.context = QgsProcessingContext()
        self.context.setProject(QgsProject.instance())
        self.feedback = CollectingFeedback()
        #layers handed to processing have to stay alive for the whole run
        self._layers: list = []
        self._output_counter = 0

    def tearDown(self):
        self._layers.clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------ inputs

    def networkLayer(self, epsg: int = fixtures.METRIC_EPSG):
        layer = fixtures.networkLayer(epsg)
        self._layers.append(layer)
        return layer

    def pointLayer(self, base: str, epsg: int = fixtures.METRIC_EPSG,
                   keep: Optional[list[int]] = None):
        layer = fixtures.pointLayer(base, epsg, keep)
        self._layers.append(layer)
        return layer

    def tempPath(self, name: str) -> str:
        return os.path.join(self.temp_dir, name)

    def outputPath(self, name: str, extension: str = 'tif') -> str:
        """A fresh path for every call.

        Tests that run the same algorithm twice to compare the results must not
        have the second run overwrite the first one's file.
        """
        self._output_counter += 1
        return os.path.join(self.temp_dir, f'{name}_{self._output_counter}.{extension}')

    def baseParameters(self, epsg: int = fixtures.METRIC_EPSG,
                       strategy: int = STRATEGY_DISTANCE) -> dict:
        """Parameters every algorithm shares.

        The direction parameters are deliberately left at their defaults - they
        are QgsVectorLayerDirector's behaviour and are covered by the QGIS test
        suite, not this one.
        """
        return {
            'GRAPH_LAYER': self.networkLayer(epsg),
            'STRATEGY': strategy,
            'SPEED_FIELD': fixtures.SPEED_FIELD,
            'DEFAULT_SPEED': DEFAULT_SPEED,
            'TOLERANCE': 0.0,
        }

    # ------------------------------------------------------------------ running

    def runAlgorithm(self, algorithm: str, parameters: dict) -> dict:
        """Run a QNEAT algorithm, failing the test if it reports an error."""
        results = processing.run(f'qneat:{algorithm}', parameters,
                                 context=self.context, feedback=self.feedback)
        if self.feedback.errors:
            self.fail(f'{algorithm} reported errors:\n  ' +
                      '\n  '.join(self.feedback.errors))
        return results

    def assertAlgorithmRaises(self, algorithm: str, parameters: dict,
                              expected_text: Optional[str] = None):
        """Assert the algorithm rejects these parameters, and how."""
        with self.assertRaises(QgsProcessingException) as caught:
            processing.run(f'qneat:{algorithm}', parameters,
                           context=self.context, feedback=QgsProcessingFeedback())
        if expected_text is not None:
            self.assertIn(expected_text.lower(), str(caught.exception).lower())
        return caught.exception

    def outputLayer(self, results: dict, key: str = 'OUTPUT'):
        value = results[key]
        #a sink writing to TEMPORARY_OUTPUT hands back the layer itself, a sink
        #writing to a path hands back the path
        layer = value if not isinstance(value, str) else \
            QgsProcessingUtils.mapLayerFromString(value, self.context)
        self.assertIsNotNone(layer, f'no output layer for {key}')
        self.assertTrue(layer.isValid(), f'output layer for {key} is invalid')
        return layer

    def outputFeatures(self, results: dict, key: str = 'OUTPUT') -> list[QgsFeature]:
        return list(self.outputLayer(results, key).getFeatures())

    # ------------------------------------------------------------------ oracle

    def solve(self, points: list[tuple[float, float]], strategy: int,
              epsg: int = fixtures.METRIC_EPSG):
        """Reference solution for these analysis points."""
        return fixtures.referenceNetwork(epsg).solve(
            points, STRATEGY_NAMES[strategy], DEFAULT_SPEED)

    def costTolerance(self, strategy: int) -> float:
        return METRE_TOLERANCE if strategy == STRATEGY_DISTANCE else SECOND_TOLERANCE

    # -------------------------------------------------------------- assertions

    def assertCost(self, actual, expected: float, strategy: int, what: str):
        self.assertIsNotNone(actual, f'{what}: expected {expected}, got NULL')
        self.assertAlmostEqual(float(actual), expected,
                               delta=self.costTolerance(strategy),
                               msg=f'{what}: cost mismatch')

    def assertNullCost(self, feature: QgsFeature, what: str):
        for field in ('entry_cost', 'network_cost', 'exit_cost', 'total_cost'):
            value = feature[field]
            self.assertTrue(value is None or (isinstance(value, float) and math.isnan(value)),
                            f'{what}: {field} should be NULL for an unreachable pair, '
                            f'got {value!r}')

    def assertPointsEqual(self, actual: tuple[float, float],
                          expected: tuple[float, float], what: str):
        self.assertAlmostEqual(actual[0], expected[0], delta=COORDINATE_TOLERANCE,
                               msg=f'{what}: x mismatch')
        self.assertAlmostEqual(actual[1], expected[1], delta=COORDINATE_TOLERANCE,
                               msg=f'{what}: y mismatch')

    def assertVertexSequence(self, geometry, expected: list[tuple[float, float]],
                             what: str):
        """The line's vertices, in order, must be the reference path."""
        actual = [(point.x(), point.y()) for point in geometry.asPolyline()]
        self.assertEqual(len(actual), len(expected),
                         f'{what}: expected {len(expected)} vertices, got {len(actual)}\n'
                         f'  actual:   {actual}\n  expected: {expected}')
        for index, (got, want) in enumerate(zip(actual, expected)):
            self.assertPointsEqual(got, want, f'{what}: vertex {index}')

    def assertFieldNames(self, layer, expected: list[str]):
        self.assertEqual([field.name() for field in layer.fields()], expected,
                         'output schema changed')

    # ----------------------------------------------------------------- rasters

    def assertRasterMatchesGolden(self, path: str, store_name: str, key: str):
        """Compare a raster against its golden record, structure first.

        The structural fields are asserted individually and before the hash, so
        that a failure names what actually differs instead of only reporting
        two hex strings that are not equal.
        """
        summary = raster_utils.summarise(path)

        store = raster_utils.GoldenStore(store_name)
        if raster_utils.blessing():
            store.record(key, summary)
            store.flush()
            return summary

        expected = store.expected(key)
        if expected is None:
            self.fail(f'no golden record for {store_name}/{key}. '
                      f'Create it with: tests/run_tests.sh --bless')

        actual_structure = summary.structural()
        for field, want in expected.items():
            if field == 'digest':
                continue
            got = actual_structure[field]
            if isinstance(want, float) and isinstance(got, float):
                self.assertAlmostEqual(got, want, places=6,
                                       msg=f'{key}: {field} changed')
            else:
                self.assertEqual(got, want, f'{key}: {field} changed')

        self.assertEqual(
            summary.digest, expected['digest'],
            f'{key}: raster contents changed. Everything structural still '
            f'matches, so this is a change in the pixel values themselves. '
            f'If it is intended, refresh with tests/run_tests.sh --bless')
        return summary

    def assertRasterSample(self, path: str, xy: tuple[float, float],
                           expected: float, delta: float, what: str):
        value = raster_utils.sample(path, *xy)
        self.assertIsNotNone(value, f'{what}: no data at {xy}')
        self.assertAlmostEqual(value, expected, delta=delta,
                               msg=f'{what}: cost surface value at {xy}')
