# -*- coding: utf-8 -*-
"""Harness smoke test: QGIS is up, the provider is registered, fixtures load."""
from __future__ import annotations

from . import fixtures, qgis_bootstrap
from .qneat_testcase import QneatTestCase


class SmokeTest(QneatTestCase):

    def test_environment(self):
        print('\n  ' + qgis_bootstrap.describeEnvironment())

    def test_provider_registered(self):
        from qgis.core import QgsApplication
        registry = QgsApplication.processingRegistry()
        provider = registry.providerById('qneat')
        self.assertIsNotNone(provider)
        names = sorted(a.name() for a in provider.algorithms())
        print('\n  algorithms: ' + ', '.join(names))
        self.assertEqual(len(names), 11)

    def test_fixtures_load(self):
        layer = self.networkLayer()
        self.assertEqual(layer.featureCount(), 40)
        self.assertEqual(layer.crs().authid(), 'EPSG:32118')
        reference = fixtures.referenceNetwork()
        self.assertEqual(len(reference.edges), 40)
        print(f'\n  edge 1 geodesic length: {reference.edgeLength(0):.4f} m')
