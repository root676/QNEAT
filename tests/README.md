# QNEAT test suite

Correctness tests for the eleven QNEAT processing algorithms, run against a
headless QGIS 4 instance.

```sh
tests/run_tests.sh                      # everything
tests/run_tests.sh -v                   # everything, verbose
tests/run_tests.sh tests.test_od_matrix # one module
tests/run_tests.sh --prefix /opt/qgis4  # a specific QGIS
tests/run_tests.sh --container          # force the containerised run
tests/run_tests.sh --bless              # refresh the raster golden files
```

No third party packages are needed. The suite is stdlib `unittest`, and the only
imports beyond QGIS itself are `numpy` and `osgeo`, both of which QNEAT already
depends on.

## How QGIS 4 is found

`run_tests.sh` probes, in order, `--prefix`, `$QGIS_PREFIX_PATH`,
`tests/qgis_prefix.local`, and then a few conventional source build and install
locations. A candidate only counts if Python can actually import `qgis.core`
from it *and* it reports major version 4 or newer, so a QGIS 3 sitting in
`/usr` is skipped rather than picked and then failed on. The winning prefix is
exported along with the matching `PYTHONPATH` and `LD_LIBRARY_PATH`, and the
suite runs with `QT_QPA_PLATFORM=offscreen`.

To pin a particular build without typing it every time:

```sh
echo /path/to/qgis4 > tests/qgis_prefix.local   # not tracked by git
```

If no local QGIS 4 qualifies, the runner falls back to podman or docker,
mounting the plugin at `/src/QNEAT` (QNEAT imports itself as a package, so the
directory name matters). Override the image with `$QNEAT_TEST_IMAGE`.

## How correctness is established

Expected values are **not** captured from a previous QNEAT run. `oracle.py` is
an independent reimplementation of the analysis, written from the fixture
geometry alone:

| what | QNEAT | oracle |
|---|---|---|
| edge length | `QgsDistanceArea`, C++ | Vincenty inverse on GRS80, written out in `oracle.py` |
| snapping | `QgsVectorLayerDirector` ties points on and splits edges | nearest point on segment, planar in layer units, same split |
| routing | `QgsGraphAnalyzer.dijkstra` | plain Dijkstra over the split graph |
| cost model | metres, or seconds via `QgsNetworkSpeedStrategy` | `length`, or `length / (km/h * 1000/3600)` |

So a bug in QNEAT cannot become the expected answer. The two agree to within a
millimetre and a millisecond across every routing test, including entry and exit
costs and full route vertex sequences.

Raster outputs cannot be derived this way, so they are checked three ways at
once — see the module docstring in `raster_utils.py`. Iso area polygons come out
of GDAL's contouring and are checked against the oracle by containment: every
vertex the reference says is reachable well within a cost level has to lie
inside the polygon for that level.

The direction parameters are deliberately **not** tested. They are
`QgsVectorLayerDirector` behaviour, covered by the QGIS test suite.

## The test network

40 edges, each a straight two vertex line, in `tests/data/network_32118.csv`.
Attributes: `edge_id`, `speed_kmh` (km/h), `length_m` (the geodesic length of
the geometry beside it, in metres) and a `note`.

```
 r4  c1---------c2---------c3---------c4---------c5          30 km/h
     |          |          |          |          |
 r3  c1---------c2---------c3---------c4---------c5--A---B   10 km/h  + spur
     |          |          |        / |          |
 r2  c1---------c2---------c3---------c4---------c5          50 km/h
     |          |  /       |          |     /    |
 r1  c1---------c2---------c3---------c4---------c5         100 km/h
    100         30         30         30        100  <- column speeds

     nodes on a 1000 m grid from (300000, 60000)
     c3r3-c3r4 carries no speed value at all
     plus a detached 4 edge square at (310000, 70000), unreachable from the grid
```

The speeds are chosen so that distance optimisation and time optimisation
*disagree*: from c1r3 to c5r3 the shortest path runs straight along row 3
(4000 m at 10 km/h, 1440 s), while the fastest drops to the 100 km/h row 1 and
comes back up (8000 m, 288 s). If a change ever made those two routes identical,
`test_time_takes_the_faster_detour` fails on purpose.

Point fixtures (`origins_*.csv`, 5 points; `destinations_*.csv`, 4 points) each
carry an integer `id_int` and a string `id_str`, so the id datatype plumbing is
covered both ways. They are positioned to exercise, in order: a point exactly on
a node, a point off the network that ties to a node, a point that ties to the
*middle* of an edge and splits it, a second node point, and a point on the
detached component.

### Two CRSs

Everything exists twice: **EPSG:32118** (NAD83 / New York Long Island, metres)
and **EPSG:2263** (the same Lambert Conformal Conic 2SP projection on the same
datum, in US survey feet). They are exact unit conversions of one another and
therefore describe the very same points on the ellipsoid.

QNEAT costs are always ellipsoidal — real metres, real seconds, never map units
— so both must return *identical* numbers. Anything that reads a map unit and
forgets to convert shows up in `test_crs_parity.py` as a factor of 3.28 and
nowhere else. That is what the second fixture is for.

Note that a point converted to feet at full float precision misses the fixture's
four decimal node coordinates by a hundredth of a millimetre, which with a
topology tolerance of zero is enough to split an edge. `toFeet()` in
`test_crs_parity.py` rounds onto the fixture grid for exactly this reason.

### Editing the fixtures

`network_32118.csv`, `origins_32118.csv` and `destinations_32118.csv` are the
masters and are meant to be edited by hand. Afterwards run

```sh
python3 tests/data/make_fixtures.py
```

which recomputes the `length_m` column from the WKT and regenerates the three
EPSG:2263 twins. It also verifies that the twins still land on the same points
on the ellipsoid.

Changing a fixture changes the raster outputs, so re-bless afterwards.

## Golden raster files

`tests/data/golden/*.json` holds, per raster output, a quantised band hash plus
the structural facts asserted separately: size, geotransform, CRS, data type,
nodata value, valid cell count and value range.

The hash is taken over values rounded to four decimals, so the last bits of a
float32 shifting between GDAL builds do not turn every raster test red while a
real change still does. When a hash goes stale for a good reason:

```sh
tests/run_tests.sh --bless
```

then read the diff under `tests/data/golden/` before committing it. A structural
field changing there is worth a second look; a digest changing on its own is the
expected shape of an intentional pixel level change.

## Layout

| file | |
|---|---|
| `run_tests.sh` | finds QGIS 4, sets the environment, launches the suite |
| `qgis_bootstrap.py` | starts headless QGIS, registers the QNEAT provider |
| `oracle.py` | the independent reference implementation, no QGIS |
| `fixtures.py` | CSV to QGIS memory layers, and to oracle structures |
| `raster_utils.py` | raster summaries, pixel probes, the golden store |
| `qneat_testcase.py` | base `TestCase`: runs algorithms, holds the assertions |
| `test_smoke.py` | the harness itself is up and the provider is registered |
| `test_shortest_path.py` | `shortestpathbetweenpoints` |
| `test_od_matrix.py` | the four OD matrix algorithms |
| `test_iso_pointcloud.py` | the two iso area pointcloud algorithms |
| `test_iso_cost_surface.py` | the two cost surface algorithms, raster outputs |
| `test_iso_areas.py` | the two iso area algorithms, raster and vector outputs |
| `test_crs_parity.py` | metres against US survey feet |
| `test_validation.py` | the guards and their messages |
