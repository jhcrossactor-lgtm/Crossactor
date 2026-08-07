"""敷地ポリゴンの各辺を番号で管理し、道路境界・隣地境界を区別する"""
from dataclasses import dataclass
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union


@dataclass
class BoundaryEdge:
    index: int
    line: LineString
    kind: str = "未設定"
    road_width_m: float | None = None

    @property
    def start(self):
        return self.line.coords[0]

    @property
    def end(self):
        return self.line.coords[1]

    @property
    def length_m(self):
        return self.line.length

    @property
    def midpoint(self):
        return self.line.interpolate(0.5, normalized=True)


def extract_edges(polygon: Polygon) -> list[BoundaryEdge]:
    coords = list(polygon.exterior.coords)
    n = len(coords) - 1
    return [
        BoundaryEdge(index=i, line=LineString([coords[i], coords[(i + 1) % n]]))
        for i in range(n)
    ]


def print_edge_table(edges: list[BoundaryEdge]) -> None:
    print()
    print("=" * 65)
    print("  敷地境界線 一覧")
    print("=" * 65)
    print(f"  {'No':>3}  {'始点 (X, Y)':>22}  {'終点 (X, Y)':>22}  {'長さ':>6}  種別")
    print("-" * 65)
    for e in edges:
        sx, sy = e.start
        ex, ey = e.end
        print(f"  {e.index:>3}  ({sx:>9.3f}, {sy:>9.3f})  ({ex:>9.3f}, {ey:>9.3f})  {e.length_m:>5.2f}m  {e.kind}")
    print("=" * 65)
    print()


def apply_boundary_types(
    edges: list[BoundaryEdge],
    road_indices: list[int],
    neighbor_indices: list[int],
    road_width: float | None = None,
) -> list[BoundaryEdge]:
    for e in edges:
        if e.index in road_indices:
            e.kind = "道路"
            e.road_width_m = road_width
        elif e.index in neighbor_indices:
            e.kind = "隣地"
        else:
            e.kind = "隣地"
    return edges


def road_edges(edges: list[BoundaryEdge]) -> list[BoundaryEdge]:
    return [e for e in edges if e.kind == "道路"]


def neighbor_edges(edges: list[BoundaryEdge]) -> list[BoundaryEdge]:
    return [e for e in edges if e.kind == "隣地"]
