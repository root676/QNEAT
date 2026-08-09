# -*- coding: utf-8 -*-
"""
***************************************************************************
    raster_utils.py
    ---------------------

    Raster comparison helpers, plus the golden file store behind them.

    Raster outputs are checked on three levels, because a hash on its own tells
    you that something changed but never whether the change is wrong:

      * the hash of the band, which catches any change at all
      * the raster's structure - size, geotransform, CRS, nodata - asserted
        separately, so a GDAL upgrade that shifts the last bits of a float does
        not leave you with nothing to read
      * individual pixels probed against the oracle, which is the only part
        that says the numbers in the raster are actually right

    When an intentional change makes the hashes stale, refresh them with

        tests/run_tests.sh --bless

    and review the resulting diff in tests/data/golden before committing it.

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

import hashlib
import json
import math
import os

from dataclasses import dataclass, asdict
from typing import Optional

import numpy

from osgeo import gdal, osr

gdal.UseExceptions()

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'golden')

#hashing rounded values rather than raw bytes: the last bits of a float32 are
#not stable across GDAL builds, while four decimals of a metre or a second are
#far finer than anything the algorithms are specified to
QUANTISATION_DECIMALS = 4


def blessing() -> bool:
    return os.environ.get('QNEAT_BLESS_GOLDEN', '0') == '1'


@dataclass
class RasterSummary:
    """Everything about a raster the tests assert on, except its pixels."""
    width: int
    height: int
    bands: int
    data_type: str
    geotransform: list[float]
    authid: str
    nodata: Optional[float]
    valid_count: int
    minimum: Optional[float]
    maximum: Optional[float]
    digest: str

    def structural(self) -> dict:
        data = asdict(self)
        data.pop('digest')
        return data


def _authid(dataset) -> str:
    projection = dataset.GetProjection()
    if not projection:
        return ''
    reference = osr.SpatialReference(wkt=projection)
    reference.AutoIdentifyEPSG()
    authority = reference.GetAuthorityName(None)
    code = reference.GetAuthorityCode(None)
    return f'{authority}:{code}' if authority and code else ''


def summarise(path: str) -> RasterSummary:
    dataset = gdal.Open(path)
    if dataset is None:
        raise AssertionError(f'could not open raster {path}')
    try:
        band = dataset.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        values = band.ReadAsArray().astype(numpy.float64)

        valid = numpy.isfinite(values)
        if nodata is not None:
            valid &= (values != nodata)

        rounded = numpy.round(numpy.where(valid, values, numpy.nan),
                              QUANTISATION_DECIMALS)
        #NaN has more than one bit pattern, so normalise the invalid cells to a
        #single sentinel before hashing
        rounded = numpy.where(numpy.isnan(rounded), -9.0e30, rounded)
        digest = hashlib.md5(numpy.ascontiguousarray(rounded, dtype='<f8')
                             .tobytes()).hexdigest()

        return RasterSummary(
            width=dataset.RasterXSize,
            height=dataset.RasterYSize,
            bands=dataset.RasterCount,
            data_type=gdal.GetDataTypeName(band.DataType),
            geotransform=[round(v, 6) for v in dataset.GetGeoTransform()],
            authid=_authid(dataset),
            nodata=nodata,
            valid_count=int(valid.sum()),
            minimum=float(numpy.min(values[valid])) if valid.any() else None,
            maximum=float(numpy.max(values[valid])) if valid.any() else None,
            digest=digest,
        )
    finally:
        dataset = None


def sample(path: str, x: float, y: float) -> Optional[float]:
    """Value of the cell containing a map coordinate, or None outside/nodata."""
    dataset = gdal.Open(path)
    try:
        geotransform = dataset.GetGeoTransform()
        column = int(math.floor((x - geotransform[0]) / geotransform[1]))
        row = int(math.floor((y - geotransform[3]) / geotransform[5]))
        if not (0 <= column < dataset.RasterXSize and 0 <= row < dataset.RasterYSize):
            return None
        band = dataset.GetRasterBand(1)
        value = float(band.ReadAsArray(column, row, 1, 1)[0][0])
        nodata = band.GetNoDataValue()
        if nodata is not None and value == nodata:
            return None
        if not math.isfinite(value):
            return None
        return value
    finally:
        dataset = None


class GoldenStore:
    """Loads and, when blessing, rewrites the expected raster summaries."""

    def __init__(self, name: str):
        self.name = name
        self.path = os.path.join(GOLDEN_DIR, f'{name}.json')
        self._data: dict = {}
        if os.path.exists(self.path):
            with open(self.path) as handle:
                self._data = json.load(handle)
        self._dirty = False

    def expected(self, key: str) -> Optional[dict]:
        return self._data.get(key)

    def record(self, key: str, summary: RasterSummary) -> None:
        self._data[key] = asdict(summary)
        self._dirty = True

    def flush(self) -> None:
        if not self._dirty:
            return
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        with open(self.path, 'w') as handle:
            json.dump(self._data, handle, indent=2, sort_keys=True)
            handle.write('\n')
        self._dirty = False
