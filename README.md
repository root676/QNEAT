# QNEAT

The QNEAT Processing plugin (short for QGIS Network Analysis Toolbox) aims to provide sophisticated QGIS Processing algorithms in the field of network, graph and accessibility analysis. The QNEAT plugin is designed as a QGIS Processing provider for the Processing toolbox. Therefore all QNEAT algorithms can be integrated into complex analytical workflows via the Processing modeler as well as processing python scripts.

## Algorithms

- **Shortest Path** (Dijkstra) between two points (pairs of coordinates obtained by using QGIS-GUI)
- **Origin-Destination Matrices** Matrix between all points of a layer (table/straight line/routed geometry).
- **ISO-Area Algorithms** Algorithms for isochrone area calculation (pointcloud, interpolation-based raster, contours and polygon)

## FAQ

# How can I cite QNEAT?
You may cite the plugin using the DOI provided at the [ResearchGate](https://doi.org/10.13140/RG.2.2.13042.02248) project-website.

# Is this QNEAT3?
QNEAT is the successor to QNEAT3, which was a plugin for QGIS3. I redesigned the plugin to work with QGIS4, dropped unnecessary parameters, merged some algorithms (eg. have iso-area contour and polygon creation in one iso-area algorithm) and reworked the interpolation functions. QNEAT3 is considered deprecated.

# Can I use QNEAT with older QNEAT3 models?

The rework on QNEAT3 broke/merged some parameters and functionalities, so QNEAT can therefore *not* be used in models that used QNEAT3. Although QNEAT features the same functionality as QNEAT3, the models must be adapted to work with QNEAT algorithms.
