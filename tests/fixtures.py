# -*- coding: utf-8 -*-
"""
***************************************************************************
    fixtures.py
    ---------------------

    Loads the CSV test datasets into QGIS memory layers and into the equivalent
    oracle structures, so both sides of every assertion start from the very same
    WKT.

    The datasets live in tests/data as plain CSV with a WKT geometry column, one
    set per CRS. See tests/README.md for the network's layout and for what each
    point is positioned to exercise.

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

import csv
import os

from dataclasses import dataclass
from typing import Optional

from qgis.core import (QgsCoordinateReferenceSystem,
                       QgsFeature,
                       QgsGeometry,
                       QgsPointXY,
                       QgsVectorLayer)

from .oracle import ReferenceEdge, ReferenceNetwork

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

#the metric master and its exact US survey foot twin
METRIC_EPSG = 32118
FOOT_EPSG = 2263
ALL_EPSG = (METRIC_EPSG, FOOT_EPSG)

NETWORK_FIELDS = (('edge_id', 'integer'), ('speed_kmh', 'double'),
                  ('length_m', 'double'), ('note', 'string'))
POINT_FIELDS = (('id_int', 'integer'), ('id_str', 'string'), ('note', 'string'))

SPEED_FIELD = 'speed_kmh'


@dataclass(frozen=True)
class FixturePoint:
    id_int: int
    id_str: str
    note: str
    xy: tuple[float, float]


_rows_cache: dict[str, list[dict]] = {}
_network_cache: dict[int, ReferenceNetwork] = {}


def _readRows(name: str) -> list[dict]:
    if name not in _rows_cache:
        with open(os.path.join(DATA_DIR, name), newline='') as handle:
            _rows_cache[name] = list(csv.DictReader(handle))
    return _rows_cache[name]


def _parsePoints(wkt: str) -> list[tuple[float, float]]:
    body = wkt[wkt.index('(') + 1:wkt.rindex(')')]
    points = []
    for pair in body.split(','):
        x, y = pair.split()
        points.append((float(x), float(y)))
    return points


def _optionalFloat(text: str) -> Optional[float]:
    text = (text or '').strip()
    return float(text) if text else None


def _memoryLayer(geometry: str, epsg: int, fields, name: str) -> QgsVectorLayer:
    definition = '&'.join([f'{geometry}?crs=EPSG:{epsg}'] +
                          [f'field={field}:{field_type}' for field, field_type in fields])
    layer = QgsVectorLayer(definition, name, 'memory')
    assert layer.isValid(), f'could not build memory layer {name}'
    return layer


def networkRows(epsg: int) -> list[dict]:
    return _readRows(f'network_{epsg}.csv')


def networkLayer(epsg: int = METRIC_EPSG) -> QgsVectorLayer:
    """The 40 edge test network as a line layer.

    A fresh layer per call - processing algorithms take ownership of what they
    are handed, and reusing one across runs invites surprises.
    """
    layer = _memoryLayer('LineString', epsg, NETWORK_FIELDS, f'network_{epsg}')
    provider = layer.dataProvider()

    features = []
    for row in networkRows(epsg):
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPolylineXY(
            [QgsPointXY(x, y) for x, y in _parsePoints(row['wkt'])]))
        feature.setAttributes([int(row['edge_id']),
                               _optionalFloat(row['speed_kmh']),
                               _optionalFloat(row['length_m']),
                               row['note']])
        features.append(feature)

    assert provider.addFeatures(features), 'could not populate the network layer'
    layer.updateExtents()
    assert layer.featureCount() == 40, f'expected 40 edges, got {layer.featureCount()}'
    return layer


def pointRows(base: str, epsg: int) -> list[FixturePoint]:
    points = []
    for row in _readRows(f'{base}_{epsg}.csv'):
        x, y = _parsePoints(row['wkt'])[0]
        points.append(FixturePoint(int(row['id_int']), row['id_str'], row['note'], (x, y)))
    return points


def pointLayer(base: str, epsg: int = METRIC_EPSG,
               keep: Optional[list[int]] = None) -> QgsVectorLayer:
    """A point layer from one of the point fixtures.

    keep selects a subset by id_int, for tests that need a smaller matrix.
    """
    layer = _memoryLayer('Point', epsg, POINT_FIELDS, f'{base}_{epsg}')
    provider = layer.dataProvider()

    features = []
    for point in pointRows(base, epsg):
        if keep is not None and point.id_int not in keep:
            continue
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*point.xy)))
        feature.setAttributes([point.id_int, point.id_str, point.note])
        features.append(feature)

    assert provider.addFeatures(features), f'could not populate {base}'
    layer.updateExtents()
    return layer


def origins(epsg: int = METRIC_EPSG) -> list[FixturePoint]:
    return pointRows('origins', epsg)


def destinations(epsg: int = METRIC_EPSG) -> list[FixturePoint]:
    return pointRows('destinations', epsg)


def referenceNetwork(epsg: int = METRIC_EPSG) -> ReferenceNetwork:
    """The same network as the oracle sees it. Cached - lengths are geodesic."""
    if epsg not in _network_cache:
        edges = []
        for row in networkRows(epsg):
            points = _parsePoints(row['wkt'])
            edges.append(ReferenceEdge(int(row['edge_id']), points[0], points[-1],
                                       _optionalFloat(row['speed_kmh'])))
        _network_cache[epsg] = ReferenceNetwork(edges, epsg)
    return _network_cache[epsg]


def crs(epsg: int) -> QgsCoordinateReferenceSystem:
    return QgsCoordinateReferenceSystem.fromEpsgId(epsg)


def storedLength(epsg: int, edge_id: int) -> float:
    """The length_m attribute of one edge, in metres."""
    for row in networkRows(epsg):
        if int(row['edge_id']) == edge_id:
            return float(row['length_m'])
    raise KeyError(f'no edge {edge_id}')
