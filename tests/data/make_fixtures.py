# -*- coding: utf-8 -*-
"""
***************************************************************************
    make_fixtures.py
    ---------------------

    Maintains the derived parts of the test fixtures. Run it after editing any
    *_32118.csv master:

        python3 tests/data/make_fixtures.py

    It does two things:

      * refreshes the length_m column of network_32118.csv from the WKT, so the
        stored length is always the geodesic length of the geometry next to it
      * regenerates the EPSG:2263 twins from the EPSG:32118 masters

    EPSG:32118 and EPSG:2263 are the same Lambert Conformal Conic 2SP
    projection on the same NAD83/GRS80 datum, differing only in linear unit, so
    the twin is an exact unit conversion by 3937/1200 and describes the very
    same points on the ellipsoid. That is what makes the CRS parity tests
    meaningful: identical costs in metres and seconds must come back from both.

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
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oracle import Projector  # noqa: E402

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

METRIC_EPSG = 32118
FOOT_EPSG = 2263

#exact definition of the US survey foot
METRES_PER_US_SURVEY_FOOT = 1200.0 / 3937.0

COORDINATE = re.compile(r'(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)')


def parseWkt(wkt: str) -> tuple[str, list[tuple[float, float]]]:
    prefix = wkt.split('(', 1)[0].strip()
    points = [(float(x), float(y)) for x, y in COORDINATE.findall(wkt)]
    return prefix, points


def formatWkt(prefix: str, points: list[tuple[float, float]], decimals: int) -> str:
    body = ', '.join(f'{x:.{decimals}f} {y:.{decimals}f}'.replace('.' + '0' * decimals, '')
                     for x, y in points)
    return f'{prefix} ({body})'


def toFeet(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(x / METRES_PER_US_SURVEY_FOOT, y / METRES_PER_US_SURVEY_FOOT) for x, y in points]


def readCsv(name: str) -> tuple[list[str], list[dict]]:
    with open(os.path.join(DATA_DIR, name), newline='') as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def writeCsv(name: str, header: list[str], rows: list[dict]) -> None:
    with open(os.path.join(DATA_DIR, name), 'w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    print(f'  wrote {name} ({len(rows)} rows)')


def refreshNetworkLengths() -> tuple[list[str], list[dict]]:
    header, rows = readCsv('network_32118.csv')
    projector = Projector.get(METRIC_EPSG)
    for row in rows:
        _, points = parseWkt(row['wkt'])
        total = sum(projector.distance(a, b) for a, b in zip(points, points[1:]))
        row['length_m'] = f'{total:.4f}'
    writeCsv('network_32118.csv', header, rows)
    return header, rows


def deriveFootTwin(source_name: str, target_name: str, source_rows: list[dict],
                   header: list[str]) -> None:
    rows = []
    for source in source_rows:
        row = dict(source)
        prefix, points = parseWkt(source['wkt'])
        #4 decimals of a US survey foot is well under a tenth of a millimetre,
        #so the twin is exact for every purpose the tests have
        row['wkt'] = formatWkt(prefix, toFeet(points), 4)
        rows.append(row)
    writeCsv(target_name, header, rows)


def main() -> int:
    print('refreshing derived fixtures')
    network_header, network_rows = refreshNetworkLengths()
    deriveFootTwin('network_32118.csv', 'network_2263.csv', network_rows, network_header)

    for base in ('origins', 'destinations'):
        header, rows = readCsv(f'{base}_32118.csv')
        deriveFootTwin(f'{base}_32118.csv', f'{base}_2263.csv', rows, header)

    #the twin must describe the same places on the ellipsoid, otherwise the
    #parity tests would compare two different networks
    metric = Projector.get(METRIC_EPSG)
    feet = Projector.get(FOOT_EPSG)
    _, metric_rows = readCsv('network_32118.csv')
    _, foot_rows = readCsv('network_2263.csv')
    worst = 0.0
    for metric_row, foot_row in zip(metric_rows, foot_rows):
        _, metric_points = parseWkt(metric_row['wkt'])
        _, foot_points = parseWkt(foot_row['wkt'])
        for metric_point, foot_point in zip(metric_points, foot_points):
            metric_lon, metric_lat = metric.toGeographic(*metric_point)
            foot_lon, foot_lat = feet.toGeographic(*foot_point)
            from oracle import geodesicMetres
            worst = max(worst, geodesicMetres(metric_lon, metric_lat, foot_lon, foot_lat))
    print(f'  twin agreement: worst node offset {worst * 1000.0:.6f} mm')
    if worst > 1e-3:
        print('ERROR: EPSG:2263 twin does not describe the same points', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
