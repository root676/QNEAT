# -*- coding: utf-8 -*-
"""
***************************************************************************
    oracle.py
    ---------------------

    Independent reference implementation of the network analysis QNEAT
    performs. Nothing in this module imports qgis - the expected values the
    tests assert against are derived here from the fixture geometry alone, so
    a wrong answer from QNEAT cannot quietly become the expected answer.

    What is reimplemented here, and why it is independent:

      * edge length      - Vincenty inverse on GRS80, written out below.
                           QNEAT gets its lengths from QgsDistanceArea, which
                           implements its own ellipsoidal formula in C++.
      * point snapping   - nearest point on a segment, planar in layer units,
                           matching what QgsVectorLayerDirector does when it
                           ties analysis points onto the network. Edges that
                           receive a tie point are split, exactly as the
                           director splits them.
      * shortest path    - a plain Dijkstra over the split graph.
      * cost model       - metres for the distance strategy, seconds for the
                           time strategy (length / (km/h * 1000/3600)).

    The only third party code involved is osgeo.osr, used solely to turn
    projected fixture coordinates into geographic ones before the geodesic is
    computed. That is a projection step, not a network analysis step, and
    osgeo is already a hard dependency of QNEAT itself.

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

import heapq
import math

from dataclasses import dataclass, field
from typing import Optional

from osgeo import osr

osr.UseExceptions()

#GRS80, the ellipsoid behind both fixture CRSs (NAD83). QNEAT hands
#crs.ellipsoidAcronym() to QgsGraphBuilder and QgsDistanceArea, so this is the
#ellipsoid its costs are measured against too.
GRS80_SEMI_MAJOR = 6378137.0
GRS80_INVERSE_FLATTENING = 298.257222101

#QgsNetworkSpeedStrategy is constructed with a 1000/3600 factor, so a km/h
#speed field yields costs in seconds.
KMH_TO_METRES_PER_SECOND = 1000.0 / 3600.0

#node identity is a rounded coordinate pair - fixture coordinates are round
#numbers in metres and exact unit conversions in feet, and tie points are
#computed here rather than read back from QGIS, so 6 decimals never collides.
NODE_PRECISION = 6

DISTANCE = 'distance'
TIME = 'time'


def geodesicMetres(lon1: float, lat1: float, lon2: float, lat2: float,
                   semi_major: float = GRS80_SEMI_MAJOR,
                   inverse_flattening: float = GRS80_INVERSE_FLATTENING) -> float:
    """Vincenty inverse solution - geodesic distance in metres on the ellipsoid.

    Written out in full rather than taken from a library so that it is a genuine
    second opinion on QgsDistanceArea. Accurate to well under a millimetre for
    the sub-kilometre separations the fixtures use.
    """
    if lon1 == lon2 and lat1 == lat2:
        return 0.0

    f = 1.0 / inverse_flattening
    a = semi_major
    b = (1.0 - f) * a

    L = math.radians(lon2 - lon1)
    U1 = math.atan((1.0 - f) * math.tan(math.radians(lat1)))
    U2 = math.atan((1.0 - f) * math.tan(math.radians(lat2)))

    sin_u1, cos_u1 = math.sin(U1), math.cos(U1)
    sin_u2, cos_u2 = math.sin(U2), math.cos(U2)

    lam = L
    sin_sigma = cos_sigma = sigma = cos_sq_alpha = cos_2sigma_m = 0.0

    for _ in range(200):
        sin_lam, cos_lam = math.sin(lam), math.cos(lam)
        sin_sigma = math.hypot(cos_u2 * sin_lam,
                               cos_u1 * sin_u2 - sin_u1 * cos_u2 * cos_lam)
        if sin_sigma == 0.0:
            return 0.0
        cos_sigma = sin_u1 * sin_u2 + cos_u1 * cos_u2 * cos_lam
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = cos_u1 * cos_u2 * sin_lam / sin_sigma
        cos_sq_alpha = 1.0 - sin_alpha * sin_alpha
        if cos_sq_alpha == 0.0:
            cos_2sigma_m = 0.0  # equatorial line
        else:
            cos_2sigma_m = cos_sigma - 2.0 * sin_u1 * sin_u2 / cos_sq_alpha
        C = f / 16.0 * cos_sq_alpha * (4.0 + f * (4.0 - 3.0 * cos_sq_alpha))
        previous_lam = lam
        lam = L + (1.0 - C) * f * sin_alpha * (
            sigma + C * sin_sigma * (
                cos_2sigma_m + C * cos_sigma * (-1.0 + 2.0 * cos_2sigma_m ** 2)))
        if abs(lam - previous_lam) < 1e-12:
            break

    u_sq = cos_sq_alpha * (a * a - b * b) / (b * b)
    A = 1.0 + u_sq / 16384.0 * (4096.0 + u_sq * (-768.0 + u_sq * (320.0 - 175.0 * u_sq)))
    B = u_sq / 1024.0 * (256.0 + u_sq * (-128.0 + u_sq * (74.0 - 47.0 * u_sq)))
    delta_sigma = B * sin_sigma * (
        cos_2sigma_m + B / 4.0 * (
            cos_sigma * (-1.0 + 2.0 * cos_2sigma_m ** 2)
            - B / 6.0 * cos_2sigma_m * (-3.0 + 4.0 * sin_sigma ** 2)
            * (-3.0 + 4.0 * cos_2sigma_m ** 2)))

    return b * A * (sigma - delta_sigma)


class Projector:
    """Projected fixture coordinates to geographic, so the geodesic can be taken.

    Cached per EPSG code; transforming a point is the hot path when the routing
    graph is built.
    """

    _cache: dict[int, 'Projector'] = {}

    def __init__(self, epsg: int):
        source = osr.SpatialReference()
        source.ImportFromEPSG(epsg)
        source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

        #the geographic CRS of the projected CRS' own datum, which is what
        #QgsDistanceArea transforms to before measuring
        geographic = source.CloneGeogCS()
        geographic.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

        self.epsg = epsg
        self.semi_major = source.GetSemiMajor()
        self.inverse_flattening = source.GetInvFlattening()
        self.linear_units = source.GetLinearUnits()
        self._transform = osr.CoordinateTransformation(source, geographic)
        self._points: dict[tuple[float, float], tuple[float, float]] = {}

    @classmethod
    def get(cls, epsg: int) -> 'Projector':
        if epsg not in cls._cache:
            cls._cache[epsg] = Projector(epsg)
        return cls._cache[epsg]

    def toGeographic(self, x: float, y: float) -> tuple[float, float]:
        key = (x, y)
        cached = self._points.get(key)
        if cached is None:
            lon, lat = self._transform.TransformPoint(x, y)[:2]
            cached = (lon, lat)
            self._points[key] = cached
        return cached

    def distance(self, p1: tuple[float, float], p2: tuple[float, float]) -> float:
        """Ellipsoidal distance in real metres between two projected points."""
        lon1, lat1 = self.toGeographic(*p1)
        lon2, lat2 = self.toGeographic(*p2)
        return geodesicMetres(lon1, lat1, lon2, lat2,
                              self.semi_major, self.inverse_flattening)


def nodeKey(point: tuple[float, float]) -> tuple[float, float]:
    return (round(point[0], NODE_PRECISION), round(point[1], NODE_PRECISION))


@dataclass
class ReferenceEdge:
    """One fixture edge: a straight two vertex line with a speed."""
    edge_id: int
    start: tuple[float, float]
    end: tuple[float, float]
    speed_kmh: Optional[float]


@dataclass
class Snap:
    """Where an analysis point ties onto the network."""
    edge_index: int
    #position along the edge, 0 at start and 1 at end
    t: float
    point: tuple[float, float]
    planar_distance: float


@dataclass
class RoutingResult:
    """Costs for one origin/destination pair, in the strategy's own unit."""
    entry_cost: float
    network_cost: float
    exit_cost: float
    total_cost: float
    #vertex sequence QNEAT writes as the route geometry, origin point first
    path: list[tuple[float, float]] = field(default_factory=list)


def _closestPointOnSegment(point: tuple[float, float],
                           start: tuple[float, float],
                           end: tuple[float, float]) -> tuple[float, tuple[float, float], float]:
    """Planar nearest point on a segment, in layer units.

    QgsVectorLayerDirector ties points onto the network planar in layer
    coordinates, not ellipsoidally, so this deliberately does the same.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0.0:
        t = 0.0
    else:
        t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
        t = min(1.0, max(0.0, t))
    closest = (start[0] + t * dx, start[1] + t * dy)
    return t, closest, math.hypot(point[0] - closest[0], point[1] - closest[1])


class ReferenceNetwork:
    """The fixture network, plus everything derived from it.

    Construct once per (fixture, CRS) pair and reuse - the geodesic length of
    every edge is computed eagerly and cached.
    """

    def __init__(self, edges: list[ReferenceEdge], epsg: int):
        self.edges = edges
        self.epsg = epsg
        self.projector = Projector.get(epsg)
        self.edge_lengths = [self.projector.distance(e.start, e.end) for e in edges]

    def edgeLength(self, edge_index: int) -> float:
        return self.edge_lengths[edge_index]

    def snap(self, point: tuple[float, float]) -> Snap:
        """Tie one point onto the network, nearest edge wins."""
        best: Optional[Snap] = None
        for index, edge in enumerate(self.edges):
            t, closest, distance = _closestPointOnSegment(point, edge.start, edge.end)
            if best is None or distance < best.planar_distance:
                best = Snap(index, t, closest, distance)
        assert best is not None, 'network has no edges'
        return best

    def solve(self, points: list[tuple[float, float]], strategy: str,
              default_speed: float) -> 'SolvedNetwork':
        return SolvedNetwork(self, points, strategy, default_speed)


class SolvedNetwork:
    """The network with analysis points tied on and edges split accordingly.

    This mirrors the graph QgsVectorLayerDirector hands to QNEAT: every tie
    point that does not land on an existing vertex becomes a new vertex, and
    the edge carrying it is split into a chain.
    """

    def __init__(self, network: ReferenceNetwork, points: list[tuple[float, float]],
                 strategy: str, default_speed: float):
        if strategy == TIME and default_speed <= 0:
            raise ValueError('default speed must be > 0 for the time strategy')

        self.network = network
        self.strategy = strategy
        self.default_speed = default_speed
        self.points = list(points)
        self.snaps = [network.snap(p) for p in points]

        #tie points per edge, so an edge carrying several of them is split at
        #every one of them rather than just the last
        splits: dict[int, list[float]] = {}
        for snap in self.snaps:
            splits.setdefault(snap.edge_index, []).append(snap.t)

        self.adjacency: dict[tuple[float, float], list[tuple[tuple[float, float], float]]] = {}

        for index, edge in enumerate(network.edges):
            positions = sorted({0.0, 1.0} | {round(t, 12) for t in splits.get(index, [])})
            speed = edge.speed_kmh if edge.speed_kmh else default_speed
            for a, b in zip(positions, positions[1:]):
                point_a = self._interpolate(edge, a)
                point_b = self._interpolate(edge, b)
                length = network.projector.distance(point_a, point_b)
                if strategy == DISTANCE:
                    cost = length
                else:
                    cost = length / (speed * KMH_TO_METRES_PER_SECOND)
                #the fixtures are undirected, matching the default direction
                self._addEdge(nodeKey(point_a), nodeKey(point_b), cost)

        #entry cost is measured ellipsoidally in real metres for every CRS,
        #then converted to seconds at the default speed for the time strategy
        self.entry_costs: list[float] = []
        self.tie_keys: list[tuple[float, float]] = []
        for point, snap in zip(self.points, self.snaps):
            metres = network.projector.distance(point, snap.point)
            if strategy == DISTANCE:
                self.entry_costs.append(metres)
            else:
                self.entry_costs.append(metres / (default_speed * KMH_TO_METRES_PER_SECOND))
            self.tie_keys.append(nodeKey(snap.point))

        self._dijkstra_cache: dict[tuple[float, float], tuple[dict, dict]] = {}

    @staticmethod
    def _interpolate(edge: ReferenceEdge, t: float) -> tuple[float, float]:
        return (edge.start[0] + t * (edge.end[0] - edge.start[0]),
                edge.start[1] + t * (edge.end[1] - edge.start[1]))

    def _addEdge(self, a, b, cost):
        if a == b:
            return
        self.adjacency.setdefault(a, []).append((b, cost))
        self.adjacency.setdefault(b, []).append((a, cost))

    def dijkstra(self, source: tuple[float, float]) -> tuple[dict, dict]:
        cached = self._dijkstra_cache.get(source)
        if cached is not None:
            return cached

        costs = {source: 0.0}
        previous: dict[tuple[float, float], Optional[tuple[float, float]]] = {source: None}
        queue = [(0.0, source)]
        settled = set()

        while queue:
            cost, node = heapq.heappop(queue)
            if node in settled:
                continue
            settled.add(node)
            for neighbour, edge_cost in self.adjacency.get(node, ()):
                candidate = cost + edge_cost
                if candidate < costs.get(neighbour, math.inf) - 1e-12:
                    costs[neighbour] = candidate
                    previous[neighbour] = node
                    heapq.heappush(queue, (candidate, neighbour))

        self._dijkstra_cache[source] = (costs, previous)
        return costs, previous

    def vertexCosts(self, point_index: int) -> dict[tuple[float, float], float]:
        """Network cost from one analysis point to every reachable vertex."""
        costs, _ = self.dijkstra(self.tie_keys[point_index])
        return costs

    def route(self, origin_index: int, destination_index: int) -> Optional[RoutingResult]:
        """Costs and route vertices for one pair, or None when unreachable."""
        origin_key = self.tie_keys[origin_index]
        destination_key = self.tie_keys[destination_index]

        if origin_index == destination_index:
            return RoutingResult(0.0, 0.0, 0.0, 0.0,
                                 [self.points[origin_index], self.points[destination_index]])

        costs, previous = self.dijkstra(origin_key)
        if destination_key not in costs:
            return None

        network_cost = costs[destination_key]
        entry = self.entry_costs[origin_index]
        exit_cost = self.entry_costs[destination_index]

        #QNEAT walks the tree backwards from the destination, so the geometry
        #runs destination point, destination tie, tree vertices, origin point.
        #Reversed here to read origin first.
        walk = [destination_key]
        node = destination_key
        while node != origin_key:
            node = previous[node]
            walk.append(node)

        path = [self.points[origin_index]]
        path.extend(reversed(walk))
        path.append(self.points[destination_index])

        return RoutingResult(entry, network_cost, exit_cost,
                             entry + network_cost + exit_cost, path)

    def isoPoints(self, origin_indices: list[int], max_cost: float
                  ) -> dict[tuple[float, float], tuple[float, int]]:
        """Vertices reachable within max_cost, as QNEAT's pointcloud output.

        Returns vertex -> (total cost, index of the origin that reached it
        cheapest). Mirrors calcIsoPoints: entry cost is added to every network
        cost, origins whose own entry cost already exceeds max_cost contribute
        nothing, and a vertex reached by several origins keeps the cheapest -
        ties going to the earlier origin, as the strict > comparison there does.
        """
        result: dict[tuple[float, float], tuple[float, int]] = {}
        for origin_index in origin_indices:
            entry = self.entry_costs[origin_index]
            if entry > max_cost:
                continue
            for vertex, cost in self.vertexCosts(origin_index).items():
                total = cost + entry
                if total > max_cost:
                    continue
                existing = result.get(vertex)
                if existing is None or existing[0] > total:
                    result[vertex] = (total, origin_index)
        return result
