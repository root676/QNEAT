# -*- coding: utf-8 -*-
"""
***************************************************************************
    qgis_bootstrap.py
    ---------------------

    Brings up a headless QGIS 4 application, initialises the Processing
    framework and registers the QNEAT provider under test.

    Normally you do not run this directly - tests/run_tests.sh works out which
    QGIS 4 installation to use, exports QGIS_PREFIX_PATH and the library paths,
    and then launches the test suite, which imports this module.

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

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(TESTS_DIR)
PLUGIN_PACKAGE = os.path.basename(PLUGIN_DIR)

_state: dict = {}


def _fail(message: str) -> 'NoReturn':  # noqa: F821
    raise RuntimeError(
        f'{message}\n\n'
        'Run the suite through tests/run_tests.sh, which locates a QGIS 4 '
        'installation and sets the environment up for you.')


def prefixPath() -> str:
    prefix = os.environ.get('QGIS_PREFIX_PATH', '')
    if not prefix:
        _fail('QGIS_PREFIX_PATH is not set.')
    if not os.path.isdir(prefix):
        _fail(f'QGIS_PREFIX_PATH points at {prefix!r}, which is not a directory.')
    return prefix


def start():
    """Start QGIS once per process and return (application, provider).

    Idempotent - every test module can call it.
    """
    if _state:
        return _state['app'], _state['provider']

    prefix = prefixPath()

    from qgis.core import Qgis, QgsApplication

    major = int(Qgis.version().split('.')[0])
    if major < 4:
        _fail(f'QNEAT requires QGIS 4, but QGIS {Qgis.version()} was loaded.')

    QgsApplication.setPrefixPath(prefix, True)
    #GUI disabled: the suite must run on a machine with no display
    app = QgsApplication([], False)
    app.initQgis()

    #the Processing framework lives with the QGIS installation, not with QNEAT
    for candidate in (os.path.join(prefix, 'python', 'plugins'),
                      os.path.join(prefix, 'share', 'qgis', 'python', 'plugins')):
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.append(candidate)

    try:
        from processing.core.Processing import Processing
    except ImportError as error:
        _fail(f'could not import the QGIS Processing framework: {error}')

    Processing.initialize()

    #QNEAT uses package relative imports, so it has to be imported as the
    #package it ships as rather than as loose modules
    parent = os.path.dirname(PLUGIN_DIR)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    import importlib
    provider_module = importlib.import_module(f'{PLUGIN_PACKAGE}.QneatProvider')
    provider = provider_module.QneatProvider()

    #the registry takes ownership on the C++ side, but the Python wrapper still
    #has to outlive it or the provider is collected out from under QGIS
    QgsApplication.processingRegistry().addProvider(provider)

    _state['app'] = app
    _state['provider'] = provider
    return app, provider


def describeEnvironment() -> str:
    from qgis.core import Qgis
    from osgeo import gdal
    from qgis.PyQt.QtCore import QT_VERSION_STR
    return (f'QGIS {Qgis.version()} | Qt {QT_VERSION_STR} | '
            f'GDAL {gdal.VersionInfo("RELEASE_NAME")} | '
            f'Python {sys.version.split()[0]}')
