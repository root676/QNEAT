# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QNEAT
                                 A QGIS plugin
 Qgis NEtwork Analysis Tool
                             -------------------
        begin                : 2017-07-09
        copyright            : (C) 2017 by Clemens Raffler
        email                : clemens.raffler@gmx.at
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load QNEAT class from file QNEAT.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .qneat import QNEAT
    return QNEAT(iface)
