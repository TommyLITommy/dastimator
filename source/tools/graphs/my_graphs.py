"""Mobjects used to represent mathematical graphs (think graph theory, not plotting)."""

from __future__ import annotations

__all__ = ["Graph", "DiGraph", "WeightedGraph"]

import itertools as it
from copy import copy
from enum import Enum
from typing import Hashable, Iterable
import networkx as nx
import numpy as np
from manim import LEFT, RIGHT, UP, DOWN, ORIGIN, UL, UR, DL, DR
from manim.animation.composition import AnimationGroup
from manim.animation.creation import Create, Uncreate, Write
from manim.animation.growing import GrowFromPoint, GrowFromEdge
from manim.mobject.geometry.arc import Dot, LabeledDot, ArcBetweenPoints
from manim.mobject.geometry.line import Line, ArrowTriangleFilledTip
from manim.mobject.mobject import Mobject, override_animate
from manim.mobject.opengl.opengl_compatibility import ConvertToOpenGL
from manim.mobject.opengl.opengl_mobject import OpenGLMobject
from manim.mobject.text.tex_mobject import MathTex
from manim.mobject.types.vectorized_mobject import VMobject
from manim.utils.color import BLACK
from manim.scene.scene import Scene
from manim.constants import DEFAULT_ARROW_TIP_LENGTH

from .node import Node, IndicateNode
from .edge import Edge
from ..consts import WEIGHT_LABEL_FONT_COLOR, WEIGHT_CONFIG, WEIGHT_SCALE, WEIGHT_LABEL_SCALE


class GraphType(Enum):
    UNDIRECTED = nx.Graph
    DIRECTED = nx.DiGraph


def _determine_graph_layout(
        nx_graph: nx.classes.graph.Graph | nx.classes.digraph.DiGraph,
        layout: str | dict = "spring",
        layout_scale: float = 2,
        layout_config: dict | None = None,
        partitions: list[list[Hashable]] | None = None,
        root_vertex: Hashable | None = None,
) -> dict:
    automatic_layouts = {
        "circular": nx.layout.circular_layout,
        "kamada_kawai": nx.layout.kamada_kawai_layout,
        "planar": nx.layout.planar_layout,
        "random": nx.layout.random_layout,
        "shell": nx.layout.shell_layout,
        "spectral": nx.layout.spectral_layout,
        "partite": nx.layout.multipartite_layout,
        "tree": _tree_layout,
        "spiral": nx.layout.spiral_layout,
        "spring": nx.layout.spring_layout,
    }

    custom_layouts = ["random", "partite", "tree"]

    if layout_config is None:
        layout_config = {}

    if isinstance(layout, dict):
        return layout
    elif layout in automatic_layouts and layout not in custom_layouts:
        auto_layout = automatic_layouts[layout](
            nx_graph, scale=layout_scale, **layout_config
        )
        # NetworkX returns a dictionary of 3D points if the dimension
        # is specified to be 3. Otherwise, it returns a dictionary of
        # 2D points, so adjusting is required.
        if layout_config.get("dim") == 3:
            return auto_layout
        else:
            return {k: np.append(v, [0]) for k, v in auto_layout.items()}
    elif layout == "tree":
        return _tree_layout(
            nx_graph, root_vertex=root_vertex, scale=layout_scale, **layout_config
        )
    elif layout == "partite":
        if partitions is None or len(partitions) == 0:
            raise ValueError(
                "The partite layout requires the 'partitions' parameter to contain the partition of the vertices",
            )
        partition_count = len(partitions)
        for i in range(partition_count):
            for v in partitions[i]:
                if nx_graph.nodes[v] is None:
                    raise ValueError(
                        "The partition must contain arrays of vertices in the graph",
                    )
                nx_graph.nodes[v]["subset"] = i
        # Add missing vertices to their own side
        for v in nx_graph.nodes:
            if "subset" not in nx_graph.nodes[v]:
                nx_graph.nodes[v]["subset"] = partition_count

        auto_layout = automatic_layouts["partite"](
            nx_graph, scale=layout_scale, **layout_config
        )
        return {k: np.append(v, [0]) for k, v in auto_layout.items()}
    elif layout == "random":
        # the random layout places coordinates in [0, 1)
        # we need to rescale manually afterwards...
        auto_layout = automatic_layouts["random"](nx_graph, **layout_config)
        for k, v in auto_layout.items():
            auto_layout[k] = 2 * layout_scale * (v - np.array([0.5, 0.5]))
        return {k: np.append(v, [0]) for k, v in auto_layout.items()}
    else:
        raise ValueError(
            f"The layout '{layout}' is neither a recognized automatic layout, "
            "nor a vertex placement dictionary.",
        )


def _tree_layout(
        T: nx.classes.graph.Graph | nx.classes.digraph.DiGraph,
        root_vertex: Hashable | None,
        scale: float | tuple | None = 2,
        vertex_spacing: tuple | None = None,
        orientation: str = "down",
):
    children = {root_vertex: list(T.neighbors(root_vertex))}

    if not nx.is_tree(T):
        raise ValueError("The tree layout must be used with trees")
    if root_vertex is None:
        raise ValueError("The tree layout requires the root_vertex parameter")

    # The following code is SageMath's tree layout implementation, taken from
    # https://github.com/sagemath/sage/blob/cc60cfebc4576fed8b01f0fc487271bdee3cefed/src/sage/graphs/graph_plot.py#L1447

    # Always make a copy of the children because they get eaten
    stack = [list(children[root_vertex]).copy()]
    stick = [root_vertex]
    parent = {u: root_vertex for u in children[root_vertex]}
    pos = {}
    obstruction = [0.0] * len(T)
    if orientation == "down":
        o = -1
    else:
        o = 1

    def slide(v, dx):
        """
        Shift the vertex v and its descendants to the right by dx.
        Precondition: v and its descendents have already had their
        positions computed.
        """
        level = [v]
        while level:
            nextlevel = []
            for u in level:
                x, y = pos[u]
                x += dx
                obstruction[y] = max(x + 1, obstruction[y])
                pos[u] = x, y
                nextlevel += children[u]
            level = nextlevel

    while stack:
        C = stack[-1]
        if not C:
            p = stick.pop()
            stack.pop()
            cp = children[p]
            y = o * len(stack)
            if not cp:
                x = obstruction[y]
                pos[p] = x, y
            else:
                x = sum(pos[c][0] for c in cp) / float(len(cp))
                pos[p] = x, y
                ox = obstruction[y]
                if x < ox:
                    slide(p, ox - x)
                    x = ox
            obstruction[y] = x + 1
            continue

        t = C.pop()
        pt = parent[t]

        ct = [u for u in list(T.neighbors(t)) if u != pt]
        for c in ct:
            parent[c] = t
        children[t] = copy(ct)

        stack.append(ct)
        stick.append(t)

    # the resulting layout is then rescaled again to fit on Manim's canvas

    x_min = min(pos.values(), key=lambda t: t[0])[0]
    x_max = max(pos.values(), key=lambda t: t[0])[0]
    y_min = min(pos.values(), key=lambda t: t[1])[1]
    y_max = max(pos.values(), key=lambda t: t[1])[1]
    center = np.array([x_min + x_max, y_min + y_max, 0]) / 2
    height = y_max - y_min
    width = x_max - x_min
    if vertex_spacing is None:
        if isinstance(scale, (float, int)) and (width > 0 or height > 0):
            sf = 2 * scale / max(width, height)
        elif isinstance(scale, tuple):
            if scale[0] is not None and width > 0:
                sw = 2 * scale[0] / width
            else:
                sw = 1

            if scale[1] is not None and height > 0:
                sh = 2 * scale[1] / height
            else:
                sh = 1

            sf = np.array([sw, sh, 0])
        else:
            sf = 1
    else:
        sx, sy = vertex_spacing
        sf = np.array([sx, sy, 0])
    return {v: (np.array([x, y, 0]) - center) * sf for v, (x, y) in pos.items()}


class GenericGraph(VMobject, metaclass=ConvertToOpenGL):
    """A graph (that is, a collection of vertices connected with edges).

    Graphs can be instantiated by passing both a list of (distinct, hashable)
    vertex names, together with list of edges (as tuples of vertex names). See
    the examples below for details.

    .. note::

        This implementation uses updaters to make the edges move with
        the vertices.

    Parameters
    ----------

    vertices
        A list of vertices. Must be hashable elements.
    edges
        A list of edges, specified as tuples ``(u, v)`` where both ``u``
        and ``v`` are vertices.
    labels
        Controls whether or not vertices are labeled. If ``False`` (the default),
        the vertices are not labeled; if ``True`` they are labeled using their
        names (as specified in ``vertices``) via :class:`~.MathTex`. Alternatively,
        custom labels can be specified by passing a dictionary whose keys are
        the vertices, and whose values are the corresponding vertex labels
        (rendered via, e.g., :class:`~.Text` or :class:`~.Tex`).
    label_fill_color
        Sets the fill color of the default labels generated when ``labels``
        is set to ``True``. Has no effect for other values of ``labels``.
    layout
        Either one of ``"spring"`` (the default), ``"circular"``, ``"kamada_kawai"``,
        ``"planar"``, ``"random"``, ``"shell"``, ``"spectral"``, ``"spiral"``, ``"tree"``, and ``"partite"``
        for automatic vertex positioning using ``networkx``
        (see `their documentation <https://networkx.org/documentation/stable/reference/drawing.html#module-networkx.drawing.layout>`_
        for more details), or a dictionary specifying a coordinate (value)
        for each vertex (key) for manual positioning.
    layout_config
        Only for automatically generated layouts. A dictionary whose entries
        are passed as keyword arguments to the automatic layout algorithm
        specified via ``layout`` of``networkx``.
        The ``tree`` layout also accepts a special parameter ``vertex_spacing``
        passed as a keyword argument inside the ``layout_config`` dictionary.
        Passing a tuple ``(space_x, space_y)`` as this argument overrides
        the value of ``layout_scale`` and ensures that vertices are arranged
        in a way such that the centers of siblings in the same layer are
        at least ``space_x`` units apart horizontally, and neighboring layers
        are spaced ``space_y`` units vertically.
    layout_scale
        The scale of automatically generated layouts: the vertices will
        be arranged such that the coordinates are located within the
        interval ``[-scale, scale]``. Some layouts accept a tuple ``(scale_x, scale_y)``
        causing the first coordinate to be in the interval ``[-scale_x, scale_x]``,
        and the second in ``[-scale_y, scale_y]``. Default: 2.
    vertex_type
        The mobject class used for displaying vertices in the scene.
    vertex_config
        Either a dictionary containing keyword arguments to be passed to
        the class specified via ``vertex_type``, or a dictionary whose keys
        are the vertices, and whose values are dictionaries containing keyword
        arguments for the mobject related to the corresponding vertex.
    vertex_mobjects
        A dictionary whose keys are the vertices, and whose values are
        mobjects to be used as vertices. Passing vertices here overrides
        all other configuration options for a vertex.
    edge_type
        The mobject class used for displaying edges in the scene.
    edge_config
        Either a dictionary containing keyword arguments to be passed
        to the class specified via ``edge_type``, or a dictionary whose
        keys are the edges, and whose values are dictionaries containing
        keyword arguments for the mobject related to the corresponding edge.
        In the case of a directed graph you can further customize the tip by adding a `tip_config` dict for global styling, or by adding the dict to a specific edge_config. See examples below.

    Examples
    --------

    First, we create a small graph and demonstrate that the edges move
    together with the vertices.

    .. manim:: MovingVertices

        class MovingVertices(Scene):
            def construct(self):
                vertices = [1, 2, 3, 4]
                edges = [(1, 2), (2, 3), (3, 4), (1, 3), (1, 4)]
                g = Graph(vertices, edges)
                self.play(Create(g))
                self.wait()
                self.play(g[1].animate.move_to([1, 1, 0]),
                          g[2].animate.move_to([-1, 1, 0]),
                          g[3].animate.move_to([1, -1, 0]),
                          g[4].animate.move_to([-1, -1, 0]))
                self.wait()

    There are several automatic positioning algorithms to choose from:

    .. manim:: GraphAutoPosition
        :save_last_frame:

        class GraphAutoPosition(Scene):
            def construct(self):
                vertices = [1, 2, 3, 4, 5, 6, 7, 8]
                edges = [(1, 7), (1, 8), (2, 3), (2, 4), (2, 5),
                         (2, 8), (3, 4), (6, 1), (6, 2),
                         (6, 3), (7, 2), (7, 4)]
                autolayouts = ["spring", "circular", "kamada_kawai",
                               "planar", "random", "shell",
                               "spectral", "spiral"]
                graphs = [Graph(vertices, edges, layout=lt).scale(0.5)
                          for lt in autolayouts]
                r1 = VGroup(*graphs[:3]).arrange()
                r2 = VGroup(*graphs[3:6]).arrange()
                r3 = VGroup(*graphs[6:]).arrange()
                self.add(VGroup(r1, r2, r3).arrange(direction=DOWN))

    Vertices can also be positioned manually:

    .. manim:: GraphManualPosition
        :save_last_frame:

        class GraphManualPosition(Scene):
            def construct(self):
                vertices = [1, 2, 3, 4]
                edges = [(1, 2), (2, 3), (3, 4), (4, 1)]
                lt = {1: [0, 0, 0], 2: [1, 1, 0], 3: [1, -1, 0], 4: [-1, 0, 0]}
                G = Graph(vertices, edges, layout=lt)
                self.add(G)

    The vertices in graphs can be labeled, and configurations for vertices
    and edges can be modified both by default and for specific vertices and
    edges.

    .. note::

        In ``edge_config``, edges can be passed in both directions: if
        ``(u, v)`` is an edge in the graph, both ``(u, v)`` as well
        as ``(v, u)`` can be used as keys in the dictionary.

    .. manim:: LabeledModifiedGraph
        :save_last_frame:

        class LabeledModifiedGraph(Scene):
            def construct(self):
                vertices = [1, 2, 3, 4, 5, 6, 7, 8]
                edges = [(1, 7), (1, 8), (2, 3), (2, 4), (2, 5),
                         (2, 8), (3, 4), (6, 1), (6, 2),
                         (6, 3), (7, 2), (7, 4)]
                g = Graph(vertices, edges, layout="circular", layout_scale=3,
                          labels=True, vertex_config={7: {"fill_color": RED}},
                          edge_config={(1, 7): {"stroke_color": RED},
                                       (2, 7): {"stroke_color": RED},
                                       (4, 7): {"stroke_color": RED}})
                self.add(g)

    You can also lay out a partite graph on columns by specifying
    a list of the vertices on each side and choosing the partite layout.

    .. note::

        All vertices in your graph which are not listed in any of the partitions
        are collected in their own partition and rendered in the rightmost column.

    .. manim:: PartiteGraph
        :save_last_frame:

        import networkx as nx

        class PartiteGraph(Scene):
            def construct(self):
                G = nx.Graph()
                G.add_nodes_from([0, 1, 2, 3])
                G.add_edges_from([(0, 2), (0,3), (1, 2)])
                graph = Graph(list(G.nodes), list(G.edges), layout="partite", partitions=[[0, 1]])
                self.play(Create(graph))

    The representation of a linear artificial neural network is facilitated
    by the use of the partite layout and defining partitions for each layer.

    .. manim:: LinearNN
        :save_last_frame:

        class LinearNN(Scene):
            def construct(self):
                edges = []
                partitions = []
                c = 0
                layers = [2, 3, 3, 2]  # the number of neurons in each layer

                for i in layers:
                    partitions.append(list(range(c + 1, c + i + 1)))
                    c += i
                for i, v in enumerate(layers[1:]):
                        last = sum(layers[:i+1])
                        for j in range(v):
                            for k in range(last - layers[i], last):
                                edges.append((k + 1, j + last + 1))

                vertices = np.arange(1, sum(layers) + 1)

                graph = Graph(
                    vertices,
                    edges,
                    layout='partite',
                    partitions=partitions,
                    layout_scale=3,
                    vertex_config={'radius': 0.20},
                )
                self.add(graph)

    The custom tree layout can be used to show the graph
    by distance from the root vertex. You must pass the root vertex
    of the tree.

    .. manim:: Tree

        import networkx as nx

        class Tree(Scene):
            def construct(self):
                G = nx.Graph()

                G.add_node("ROOT")

                for i in range(5):
                    G.add_node("Child_%i" % i)
                    G.add_node("Grandchild_%i" % i)
                    G.add_node("Greatgrandchild_%i" % i)

                    G.add_edge("ROOT", "Child_%i" % i)
                    G.add_edge("Child_%i" % i, "Grandchild_%i" % i)
                    G.add_edge("Grandchild_%i" % i, "Greatgrandchild_%i" % i)

                self.play(Create(
                    Graph(list(G.nodes), list(G.edges), layout="tree", root_vertex="ROOT")))

    The following code sample illustrates the use of the ``vertex_spacing``
    layout parameter specific to the ``"tree"`` layout. As mentioned
    above, setting ``vertex_spacing`` overrides the specified value
    for ``layout_scale``, and as such it is harder to control the size
    of the mobject. However, we can adjust the captured frame and
    zoom out by using a :class:`.MovingCameraScene`::

        class LargeTreeGeneration(MovingCameraScene):
            DEPTH = 4
            CHILDREN_PER_VERTEX = 3
            LAYOUT_CONFIG = {"vertex_spacing": (0.5, 1)}
            VERTEX_CONF = {"radius": 0.25, "color": BLUE_B, "fill_opacity": 1}

            def expand_vertex(self, g, vertex_id: str, depth: int):
                new_vertices = [f"{vertex_id}/{i}" for i in range(self.CHILDREN_PER_VERTEX)]
                new_edges = [(vertex_id, child_id) for child_id in new_vertices]
                g.add_edges(
                    *new_edges,
                    vertex_config=self.VERTEX_CONF,
                    positions={
                        k: g.vertices[vertex_id].get_center() + 0.1 * DOWN for k in new_vertices
                    },
                )
                if depth < self.DEPTH:
                    for child_id in new_vertices:
                        self.expand_vertex(g, child_id, depth + 1)

                return g

            def construct(self):
                g = Graph(["ROOT"], [], vertex_config=self.VERTEX_CONF)
                g = self.expand_vertex(g, "ROOT", 1)
                self.add(g)

                self.play(
                    g.animate.change_layout(
                        "tree",
                        root_vertex="ROOT",
                        layout_config=self.LAYOUT_CONFIG,
                    )
                )
                self.play(self.camera.auto_zoom(g, margin=1), run_time=0.5)
    """
    DEFAULT_TIP_SCALE_FACTOR = 0.35
    DEFAULT_TIP_CONFIG = {"tip_shape": ArrowTriangleFilledTip,
                          "tip_length": DEFAULT_ARROW_TIP_LENGTH * DEFAULT_TIP_SCALE_FACTOR,
                          "tip_width": DEFAULT_ARROW_TIP_LENGTH * DEFAULT_TIP_SCALE_FACTOR * 1.2}

    def __init__(
            self,
            vertices: list[Hashable],
            edges: list[tuple[Hashable, Hashable]],
            labels: bool | dict = False,
            label_fill_color: str = BLACK,
            layout: str | dict = "spring",
            layout_scale: float | tuple = 2,
            layout_config: dict | None = None,
            vertex_type: type[Mobject] = Dot,
            vertex_config: dict | None = None,
            vertex_mobjects: dict | None = None,
            edge_type: type[Mobject] = Line,
            partitions: list[list[Hashable]] | None = None,
            root_vertex: Hashable | None = None,
            edge_config: dict | None = None,
            graph_type: GraphType = GraphType.UNDIRECTED,
    ) -> None:
        super().__init__()
        self.graph_type = graph_type

        if graph_type == GraphType.UNDIRECTED:
            nx_graph = nx.Graph()
        elif graph_type == GraphType.DIRECTED:
            nx_graph = nx.DiGraph()
        else:
            raise NotImplementedError("graph_type must be a GraphType")

        nx_graph.add_nodes_from(vertices)
        nx_graph.add_edges_from(edges)
        self._graph = nx_graph

        self._layout = _determine_graph_layout(
            nx_graph,
            layout=layout,
            layout_scale=layout_scale,
            layout_config=layout_config,
            partitions=partitions,
            root_vertex=root_vertex,
        )

        if isinstance(labels, dict):
            self._labels = labels
        elif isinstance(labels, bool):
            if labels:
                self._labels = {
                    v: MathTex(v, fill_color=label_fill_color) for v in vertices
                }
            else:
                self._labels = {}

        if self._labels and vertex_type is Dot:
            vertex_type = LabeledDot

        if vertex_mobjects is None:
            vertex_mobjects = {}

        # build vertex_config
        if vertex_config is None:
            vertex_config = {}
        default_vertex_config = {}
        if vertex_config:
            default_vertex_config = {
                k: v for k, v in vertex_config.items() if k not in vertices
            }
        self._vertex_config = {
            v: vertex_config.get(v, copy(default_vertex_config)) for v in vertices
        }
        self.default_vertex_config = default_vertex_config
        for v, label in self._labels.items():
            self._vertex_config[v]["label"] = label

        self.vertices = {v: vertex_type(**self._vertex_config[v]) for v in vertices}
        self.vertices.update(vertex_mobjects)
        for v in self.vertices:
            self[v].move_to(self._layout[v])

        # build edge_config
        if edge_config is None:
            edge_config = {}
        default_edge_config = {}
        if edge_config:
            default_edge_config = {k: v for k, v in edge_config.items()
                                   if k not in edges and k[::-1] not in edges and k != "tip_config"}

        directed_graph = graph_type == GraphType.DIRECTED
        self.default_edge_config = default_edge_config

        self.edges = {}
        self._edge_config = {}
        self._tip_config = {}
        self.default_tip_config = self.DEFAULT_TIP_CONFIG
        if directed_graph:
            if "tip_config" in edge_config:
                self.default_tip_config = {**self.default_tip_config, **edge_config["tip_config"]}
        for e in edges:
            self._add_edge_config(e, edge_config)
            if not directed_graph and (e[1], e[0]) in self.edges:
                self.edges[e] = self.edges[(e[1], e[0])]
                continue

            self.edges[e] = self.create_edge(edge_type, *e)
            if directed_graph:
                self.edges[e] = self.edges[e].add_tip(**self._tip_config[e])

        self.add(*self.vertices.values())
        self.add(*self.edges.values())

        self.add_updater(self.update_edges)

    def _add_edge_config(self, e, edge_config):
        directed_graph = self.graph_type == GraphType.DIRECTED
        if e in edge_config:
            self._edge_config[e] = {k: v for k, v in edge_config[e].items() if k != "tip_config"}
            if directed_graph and "tip_config" in edge_config[e]:
                self._tip_config[e] = {**self.default_tip_config, **edge_config[e]["tip_config"]}

        elif e[::-1] in edge_config and not directed_graph:
            self._edge_config[e] = {k: v for k, v in edge_config[e[::-1]].items() if k != "tip_config"}
        else:
            if list(edge_config.keys()) and type(list(edge_config.keys())[0]) != tuple:
                self._edge_config[e] = {k: v for k, v in edge_config.items() if k != "tip_config"}
                if directed_graph and "tip_config" in edge_config:
                    self._tip_config[e] = {**self.default_tip_config, **edge_config["tip_config"]}
                else:
                    self._tip_config[e] = copy(self.default_tip_config)
            else:
                self._edge_config[e] = copy(self.default_edge_config)
                if directed_graph:
                    self._tip_config[e] = copy(self.default_tip_config)

    def __getitem__(self: Graph, v: Hashable) -> Mobject:
        return self.vertices[v]

    def _create_vertex(
            self,
            vertex: Hashable,
            position: np.ndarray | None = None,
            label: bool = False,
            label_fill_color: str = BLACK,
            vertex_type: type[Mobject] = Dot,
            vertex_config: dict | None = None,
            vertex_mobject: dict | None = None,
    ) -> tuple[Hashable, np.ndarray, dict, Mobject]:
        if position is None:
            position = self.get_center()

        if vertex_config is None:
            vertex_config = {}

        if vertex in self.vertices:
            raise ValueError(
                f"Vertex identifier '{vertex}' is already used for a vertex in this graph.",
            )

        if label is True:
            label = MathTex(vertex, fill_color=label_fill_color)
        elif vertex in self._labels:
            label = self._labels[vertex]
        elif not isinstance(label, (Mobject, OpenGLMobject)):
            label = None

        base_vertex_config = copy(self.default_vertex_config)
        base_vertex_config.update(vertex_config)
        vertex_config = base_vertex_config

        if label is not None:
            vertex_config["label"] = label
            if vertex_type is Dot:
                vertex_type = LabeledDot

        if vertex_mobject is None:
            vertex_mobject = vertex_type(**vertex_config)

        vertex_mobject.move_to(position)

        return (vertex, position, vertex_config, vertex_mobject)

    def _add_created_vertex(
            self,
            vertex: Hashable,
            position: np.ndarray,
            vertex_config: dict,
            vertex_mobject: Mobject,
    ) -> Mobject:
        if vertex in self.vertices:
            raise ValueError(
                f"Vertex identifier '{vertex}' is already used for a vertex in this graph.",
            )

        self._graph.add_node(vertex)
        self._layout[vertex] = position

        if "label" in vertex_config:
            self._labels[vertex] = vertex_config["label"]

        self._vertex_config[vertex] = vertex_config

        self.vertices[vertex] = vertex_mobject
        self.vertices[vertex].move_to(position)
        self.add(self.vertices[vertex])

        return self.vertices[vertex]

    def _add_vertex(
            self,
            vertex: Hashable,
            position: np.ndarray | None = None,
            label: bool = False,
            label_fill_color: str = BLACK,
            vertex_type: type[Mobject] = Dot,
            vertex_config: dict | None = None,
            vertex_mobject: dict | None = None,
    ) -> Mobject:
        """Add a vertex to the graph.

        Parameters
        ----------

        vertex
            A hashable vertex identifier.
        position
            The coordinates where the new vertex should be added. If ``None``, the center
            of the graph is used.
        label
            Controls whether or not the vertex is labeled. If ``False`` (the default),
            the vertex is not labeled; if ``True`` it is labeled using its
            names (as specified in ``vertex``) via :class:`~.MathTex`. Alternatively,
            any :class:`~.Mobject` can be passed to be used as the label.
        label_fill_color
            Sets the fill color of the default labels generated when ``labels``
            is set to ``True``. Has no effect for other values of ``label``.
        vertex_type
            The mobject class used for displaying vertices in the scene.
        vertex_config
            A dictionary containing keyword arguments to be passed to
            the class specified via ``vertex_type``.
        vertex_mobject
            The mobject to be used as the vertex. Overrides all other
            vertex customization options.
        """
        return self._add_created_vertex(
            *self._create_vertex(
                vertex=vertex,
                position=position,
                label=label,
                label_fill_color=label_fill_color,
                vertex_type=vertex_type,
                vertex_config=vertex_config,
                vertex_mobject=vertex_mobject,
            )
        )

    def _create_vertices(
            self: Graph,
            *vertices: Hashable,
            positions: dict | None = None,
            labels: bool = False,
            label_fill_color: str = BLACK,
            vertex_type: type[Mobject] = Dot,
            vertex_config: dict | None = None,
            vertex_mobjects: dict | None = None,
    ) -> Iterable[tuple[Hashable, np.ndarray, dict, Mobject]]:
        if positions is None:
            positions = {}
        if vertex_mobjects is None:
            vertex_mobjects = {}

        graph_center = self.get_center()
        base_positions = {v: graph_center for v in vertices}
        base_positions.update(positions)
        positions = base_positions

        if isinstance(labels, bool):
            labels = {v: labels for v in vertices}
        else:
            assert isinstance(labels, dict)
            base_labels = {v: False for v in vertices}
            base_labels.update(labels)
            labels = base_labels

        if vertex_config is None:
            vertex_config = copy(self.default_vertex_config)

        assert isinstance(vertex_config, dict)
        base_vertex_config = copy(self.default_vertex_config)
        base_vertex_config.update(
            {key: val for key, val in vertex_config.items() if key not in vertices},
        )
        vertex_config = {
            v: (vertex_config[v] if v in vertex_config else copy(base_vertex_config))
            for v in vertices
        }

        return [
            self._create_vertex(
                v,
                position=positions[v],
                label=labels[v],
                label_fill_color=label_fill_color,
                vertex_type=vertex_type,
                vertex_config=vertex_config[v],
                vertex_mobject=vertex_mobjects[v] if v in vertex_mobjects else None,
            )
            for v in vertices
        ]

    def add_vertices(
            self: Graph,
            *vertices: Hashable,
            positions: dict | None = None,
            labels: bool = False,
            label_fill_color: str = BLACK,
            vertex_type: type[Mobject] = Dot,
            vertex_config: dict | None = None,
            vertex_mobjects: dict | None = None,
    ):
        """Add a list of vertices to the graph.

        Parameters
        ----------

        vertices
            Hashable vertex identifiers.
        positions
            A dictionary specifying the coordinates where the new vertices should be added.
            If ``None``, all vertices are created at the center of the graph.
        labels
            Controls whether or not the vertex is labeled. If ``False`` (the default),
            the vertex is not labeled; if ``True`` it is labeled using its
            names (as specified in ``vertex``) via :class:`~.MathTex`. Alternatively,
            any :class:`~.Mobject` can be passed to be used as the label.
        label_fill_color
            Sets the fill color of the default labels generated when ``labels``
            is set to ``True``. Has no effect for other values of ``labels``.
        vertex_type
            The mobject class used for displaying vertices in the scene.
        vertex_config
            A dictionary containing keyword arguments to be passed to
            the class specified via ``vertex_type``.
        vertex_mobjects
            A dictionary whose keys are the vertex identifiers, and whose
            values are mobjects that should be used as vertices. Overrides
            all other vertex customization options.
        """
        return [
            self._add_created_vertex(*v)
            for v in self._create_vertices(
                *vertices,
                positions=positions,
                labels=labels,
                label_fill_color=label_fill_color,
                vertex_type=vertex_type,
                vertex_config=vertex_config,
                vertex_mobjects=vertex_mobjects,
            )
        ]

    @override_animate(add_vertices)
    def _add_vertices_animation(self, *args, anim_args=None, **kwargs):
        if anim_args is None:
            anim_args = {}

        animation = anim_args.pop("animation", Create)

        vertex_mobjects = self._create_vertices(*args, **kwargs)

        def on_finish(scene: Scene):
            for v in vertex_mobjects:
                scene.remove(v[-1])
                self._add_created_vertex(*v)

        return AnimationGroup(
            *(animation(v[-1], **anim_args) for v in vertex_mobjects),
            group=self,
            _on_finish=on_finish,
        )

    def _remove_vertex(self, vertex):
        """Remove a vertex (as well as all incident edges) from the graph.

        Parameters
        ----------

        vertex
            The identifier of a vertex to be removed.

        Returns
        -------

        Group
            A mobject containing all removed objects.

        """
        if vertex not in self.vertices:
            raise ValueError(
                f"The graph does not contain a vertex with identifier '{vertex}'",
            )

        self._graph.remove_node(vertex)
        self._layout.pop(vertex)
        if vertex in self._labels:
            self._labels.pop(vertex)
        self._vertex_config.pop(vertex)

        edge_tuples = [e for e in self.edges if vertex in e]
        for e in edge_tuples:
            self._edge_config.pop(e)
        to_remove = [self.edges.pop(e) for e in edge_tuples]
        to_remove.append(self.vertices.pop(vertex))

        self.remove(*to_remove)
        return self.get_group_class()(*to_remove)

    def remove_vertices(self, *vertices):
        """Remove several vertices from the graph.

        Parameters
        ----------

        vertices
            Vertices to be removed from the graph.

        Examples
        --------
        ::

            >>> G = Graph([1, 2, 3], [(1, 2), (2, 3)])
            >>> removed = G.remove_vertices(2, 3); removed
            VGroup(Line, Line, Dot, Dot)
            >>> G
            Undirected graph on 1 vertices and 0 edges

        """
        mobjects = []
        for v in vertices:
            mobjects.extend(self._remove_vertex(v).submobjects)
        return self.get_group_class()(*mobjects)

    @override_animate(remove_vertices)
    def _remove_vertices_animation(self, *vertices, anim_args=None):
        if anim_args is None:
            anim_args = {}

        animation = anim_args.pop("animation", Uncreate)

        mobjects = self.remove_vertices(*vertices)
        return AnimationGroup(
            *(animation(mobj, **anim_args) for mobj in mobjects), group=self
        )

    def _add_edge(
            self,
            edge: tuple[Hashable, Hashable],
            edge_type: type[Mobject] = Edge,
            edge_config: dict | None = None,
    ):
        """Add a new edge to the graph.

        Parameters
        ----------

        edge
            The edge (as a tuple of vertex identifiers) to be added. If a non-existing
            vertex is passed, a new vertex with default settings will be created. Create
            new vertices yourself beforehand to customize them.
        edge_type
            The mobject class used for displaying edges in the scene.
        edge_config
            A dictionary containing keyword arguments to be passed
            to the class specified via ``edge_type``.

        Returns
        -------
        Group
            A group containing all newly added vertices and edges.

        """
        added_mobjects = []
        for v in edge:
            if v not in self.vertices:
                added_mobjects.append(self._add_vertex(v))
        u, v = edge

        self._graph.add_edge(u, v)

        self.edges[(u, v)] = self.create_edge(edge_type, u, v)
        if self.graph_type == GraphType.DIRECTED:
            self.edges[(u, v)] = self.edges[(u, v)].add_tip(**self._tip_config[(u, v)])

        self.add(self.edges[(u, v)])
        added_mobjects.append(self.edges[(u, v)])
        self.set_z_index(self.z_index)
        return self.get_group_class()(*added_mobjects)

    def create_edge(self, edge_type, u, v):
        """Create an edge mobject between two vertices."""
        start, end = self[u], self[v]
        if edge_type is not Edge:
            start, end = start.get_center(), end.get_center()

        if self.graph_type == GraphType.UNDIRECTED:
            edge_mobject = edge_type(start, end, z_index=-1,
                                     **self._edge_config[(u, v)])
        else:
            edge_len = np.linalg.norm(self[u].get_center() - self[v].get_center()
                                      ) - (self[v].width + self[u].width) / 2
            edge_mobject = edge_type(start, end, z_index=-1,
                                     **self._edge_config[(u, v)])
            edge_mobject.put_start_and_end_on(ORIGIN, [edge_len, 0, 0])
            edge_mobject.next_to(self[u], RIGHT, buff=0)
            u_v_angle = np.arctan2(self[v].get_center()[1] - self[u].get_center()[1],
                                   self[v].get_center()[0] - self[u].get_center()[0])
            edge_mobject.rotate(u_v_angle, about_point=self[u].get_center())
        return edge_mobject

    def add_edges(
            self,
            *edges: tuple[Hashable, Hashable],
            edge_type: type[Mobject] = Edge,
            edge_config: dict | None = None,
            **kwargs,
    ):
        """Add new edges to the graph.

        Parameters
        ----------

        edges
            Edges (as tuples of vertex identifiers) to be added. If a non-existing
            vertex is passed, a new vertex with default settings will be created. Create
            new vertices yourself beforehand to customize them.
        edge_type
            The mobject class used for displaying edges in the scene.
        edge_config
            A dictionary either containing keyword arguments to be passed
            to the class specified via ``edge_type``, or a dictionary
            whose keys are the edge tuples, and whose values are dictionaries
            containing keyword arguments to be passed for the construction
            of the corresponding edge.
        kwargs
            Any further keyword arguments are passed to :meth:`.add_vertices`
            which is used to create new vertices in the passed edges.

        Returns
        -------
        Group
            A group containing all newly added vertices and edges.

        """
        if edge_config is None:
            edge_config = {}

        for e in edges:
            self._add_edge_config(e, edge_config)

        edge_vertices = set(it.chain(*edges))
        new_vertices = [v for v in edge_vertices if v not in self.vertices]
        added_vertices = self.add_vertices(*new_vertices, **kwargs)

        added_mobjects = sum((self._add_edge(edge, edge_type=edge_type, edge_config=self._edge_config[edge],
                                             ).submobjects for edge in edges), added_vertices, )
        return self.get_group_class()(*added_mobjects)

    @override_animate(add_edges)
    def _add_edges_animation(self, *args, anim_args=None, **kwargs):
        if anim_args is None:
            anim_args = {}
        animation = anim_args.pop("animation", Create)

        mobjects = self.add_edges(*args, **kwargs)
        return AnimationGroup(*(animation(mobj, **anim_args) for mobj in mobjects), group=self)

    def _remove_edge(self, edge: tuple[Hashable]):
        """Remove an edge from the graph.

        Parameters
        ----------

        edge
            The edge (i.e., a tuple of vertex identifiers) to be removed from the graph.

        Returns
        -------

        Mobject
            The removed edge.

        """
        if edge not in self.edges:
            edge = edge[::-1]
            if edge not in self.edges:
                raise ValueError(f"The graph does not contain a edge '{edge}'")

        edge_mobject = self.edges.pop(edge)

        self._graph.remove_edge(*edge)
        self._edge_config.pop(edge, None)

        self.remove(edge_mobject)
        return edge_mobject

    def remove_edges(self, *edges: tuple[Hashable]):
        """Remove several edges from the graph.

        Parameters
        ----------
        edges
            Edges to be removed from the graph.

        Returns
        -------
        Group
            A group containing all removed edges.

        """
        edge_mobjects = [self._remove_edge(edge) for edge in edges]
        return self.get_group_class()(*edge_mobjects)

    @override_animate(remove_edges)
    def _remove_edges_animation(self, *edges, anim_args=None):
        if anim_args is None:
            anim_args = {}

        animation = anim_args.pop("animation", Uncreate)

        mobjects = self.remove_edges(*edges)
        return AnimationGroup(*(animation(mobj, **anim_args) for mobj in mobjects))

    def set_z_index(self, z_index_value: float, **kwargs) -> Graph:
        """Sets the z-index of the graph.

        Parameters
        ----------
        z_index_value
            The z-index value to be set.
        kwargs
            Further keyword arguments to be passed to :meth:`.Mobject.set_z_index`.

        Returns
        -------
        Graph
            The graph itself.

        """
        super().set_z_index(z_index_value, **kwargs)
        for edge in self.edges.values():
            if isinstance(edge, Edge):
                edge.fix_z_index()
        return self

    @staticmethod
    def from_networkx(
            nxgraph: nx.classes.graph.Graph | nx.classes.digraph.DiGraph, **kwargs
    ) -> Graph:
        """Build a :class:`~.Graph` from a given ``networkx`` graph.

        Parameters
        ----------

        nxgraph
            A ``networkx`` graph.
        **kwargs
            Keywords to be passed to the constructor of :class:`~.Graph`.

        Examples
        --------

        .. manim:: ImportNetworkxGraph

            import networkx as nx

            nxgraph = nx.erdos_renyi_graph(14, 0.5)

            class ImportNetworkxGraph(Scene):
                def construct(self):
                    G = Graph.from_networkx(nxgraph, layout="spring", layout_scale=3.5)
                    self.play(Create(G))
                    self.play(*[G[v].animate.move_to(5*RIGHT*np.cos(ind/7 * PI) +
                                                     3*UP*np.sin(ind/7 * PI))
                                for ind, v in enumerate(G.vertices)])
                    self.play(Uncreate(G))

        """
        graph_type = GraphType(type(nxgraph))
        if graph_type == GraphType.UNDIRECTED:
            return Graph(list(nxgraph.nodes), list(nxgraph.edges), **kwargs)
        elif graph_type == GraphType.DIRECTED:
            return DiGraph(list(nxgraph.nodes), list(nxgraph.edges), **kwargs)

    def change_layout(
            self,
            layout: str | dict = "spring",
            layout_scale: float = 2,
            layout_config: dict | None = None,
            partitions: list[list[Hashable]] | None = None,
            root_vertex: Hashable | None = None,
    ) -> Graph:
        """Change the layout of this graph.

        See the documentation of :class:`~.Graph` for details about the
        keyword arguments.

        Examples
        --------

        .. manim:: ChangeGraphLayout

            class ChangeGraphLayout(Scene):
                def construct(self):
                    G = Graph([1, 2, 3, 4, 5], [(1, 2), (2, 3), (3, 4), (4, 5)],
                              layout={1: [-2, 0, 0], 2: [-1, 0, 0], 3: [0, 0, 0],
                                      4: [1, 0, 0], 5: [2, 0, 0]}
                              )
                    self.play(Create(G))
                    self.play(G.animate.change_layout("circular"))
                    self.wait()
        """
        self._layout = _determine_graph_layout(
            self._graph,
            layout=layout,
            layout_scale=layout_scale,
            layout_config=layout_config,
            partitions=partitions,
            root_vertex=root_vertex,
        )
        for v in self.vertices:
            self[v].move_to(self._layout[v])
        return self


class Graph(GenericGraph):
    """
    Create an undirected graph
    """

    def __init__(
            self,
            vertices: list[Hashable],
            edges: list[tuple[Hashable, Hashable]],
            labels: bool | dict = False,
            label_fill_color: str = BLACK,
            layout: str | dict = "spring",
            layout_scale: float | tuple = 2,
            layout_config: dict | None = None,
            vertex_type: type[Mobject] = Dot,
            vertex_config: dict | None = None,
            vertex_mobjects: dict | None = None,
            edge_type: type[Mobject] = Line,
            partitions: list[list[Hashable]] | None = None,
            root_vertex: Hashable | None = None,
            edge_config: dict | None = None,
    ) -> None:
        super().__init__(
            vertices,
            edges,
            labels,
            label_fill_color,
            layout,
            layout_scale,
            layout_config,
            vertex_type,
            vertex_config,
            vertex_mobjects,
            edge_type,
            partitions,
            root_vertex,
            edge_config,
            graph_type=GraphType.UNDIRECTED,
        )

    def update_edges(self, graph):
        for (u, v), edge in graph.edges.items():
            # Undirected graph has a Line edge
            edge.put_start_and_end_on(graph[u].get_center(), graph[v].get_center())

    def __repr__(self: Graph) -> str:
        return f"Undirected graph on {len(self.vertices)} vertices and {len(self.edges)} edges"


class DiGraph(GenericGraph):
    """
    A directed graph

    The arrows move with the vertices by default.

    .. manim:: MovingDiGraph

        class MovingDiGraph(Scene):
            def construct(self):
                vertices = [1, 2, 3, 4]
                edges = [(1, 2), (2, 3), (3, 4), (1, 3), (1, 4)]

                g = DiGraph(vertices, edges)

                self.add(g)
                self.play(
                    g[1].animate.move_to([1, 1, 1]),
                    g[2].animate.move_to([-1, 1, 2]),
                    g[3].animate.move_to([1, -1, -1]),
                    g[4].animate.move_to([-1, -1, 0]),
                )
                self.wait()

    You can customize the edges and arrow tips globally or locally

    .. manim:: CustomDiGraph

        class CustomDiGraph(Scene):
            def construct(self):
                vertices = [i for i in range(5)]
                edges = [
                    (0, 1),
                    (1, 2),
                    (3, 2),
                    (3, 4),
                ]

                edge_config = {
                    "stroke_width": 2,
                    "tip_config": {"tip_length": 0.1, "tip_width": 0.05},
                    (3, 4): {"color": RED, "tip_config": {"tip_length": 0.5, "tip_width": 0.5}},
                }

                g = DiGraph(
                    vertices,
                    edges,
                    labels=True,
                    layout="circular",
                    edge_config=edge_config,
                ).scale(1.4)

                self.play(Create(g))
                self.wait()

    Since this implementation respects the labels boundary you can also use it for an undirected moving graph with labels

    .. manim:: UndirectedMovingDiGraph

        class UndirectedMovingDiGraph(Scene):
            def construct(self):
                vertices = [i for i in range(5)]
                edges = [
                    (0, 1),
                    (1, 2),
                    (3, 2),
                    (3, 4),
                ]

                edge_config = {
                    "stroke_width": 2,
                    "tip_config": {"tip_length": 0, "tip_width": 0},
                    (3, 4): {"color": RED},
                }

                g = DiGraph(
                    vertices,
                    edges,
                    labels=True,
                    layout="circular",
                    edge_config=edge_config,
                ).scale(1.4)

                self.play(Create(g))
                self.wait()

                self.play(
                    g[1].animate.move_to([1, 1, 1]),
                    g[2].animate.move_to([-1, 1, 2]),
                    g[3].animate.move_to([-1.5, -1.5, -1]),
                    g[4].animate.move_to([1, -2, -1]),
                )
                self.wait()

    """

    def __init__(
            self,
            vertices: list[Hashable],
            edges: list[tuple[Hashable, Hashable]],
            labels: bool | dict = False,
            label_fill_color: str = BLACK,
            layout: str | dict = "spring",
            layout_scale: float | tuple = 2,
            layout_config: dict | None = None,
            vertex_type: type[Mobject] = Node,
            vertex_config: dict | None = None,
            vertex_mobjects: dict | None = None,
            edge_type: type[Mobject] = Line,
            partitions: list[list[Hashable]] | None = None,
            root_vertex: Hashable | None = None,
            edge_config: dict | None = None,
    ) -> None:
        super().__init__(
            vertices,
            edges,
            labels,
            label_fill_color,
            layout,
            layout_scale,
            layout_config,
            vertex_type,
            vertex_config,
            vertex_mobjects,
            edge_type,
            partitions,
            root_vertex,
            edge_config,
            graph_type=GraphType.DIRECTED,
        )

    def update_edges(self, graph):
        for (u, v), edge in graph.edges.items():
            edge_type = type(edge)
            tip = edge.pop_tips()

            new_edge = self.create_edge(edge_type, u, v).set_z_index(edge.z_index)
            if isinstance(edge, Edge):
                new_edge.fix_z_index()

            edge.become(new_edge)
            if len(tip) > 0:
                edge.add_tip(tip[0])

            edge.set_color(edge.get_color())

    def __repr__(self: DiGraph) -> str:
        return f"Directed graph on {len(self.vertices)} vertices and {len(self.edges)} edges"


class WeightedGraph(DiGraph):
    def __init__(self, vertices: list[Hashable], edges: list[tuple[Hashable, Hashable]],
                 weights: dict[tuple[Hashable, Hashable], float] = None, *args, **kwargs) -> None:
        if "vertex_type" not in kwargs:
            kwargs["vertex_type"] = Node
        kwargs["edge_type"] = Edge
        # build vertex_config
        self.weights_config = kwargs.get("weights_config", {})
        edge_config = kwargs.get("edge_config", {}).copy()
        if weights is not None:
            if not isinstance(next(iter(edge_config), None), tuple):
                kwargs["edge_config"] = {edge: {**edge_config, **{"weight": weight}} for edge, weight in
                                         weights.items()}
            else:
                kwargs["edge_config"] = {edge: {**edge_config[edge], **{"weight": weight}} for edge, weight in
                                         weights.items()}

        super().__init__(vertices, edges, *args, **kwargs)

        relative_node = next(iter(self.vertices.values()))

        for edge in self.edges.values():
            if isinstance(edge, Edge) and edge.weight_mob is not None:
                edge.weight_mob.scale_to_fit_height(relative_node.height * WEIGHT_SCALE)
                edge.weight_mob[1].scale(WEIGHT_LABEL_SCALE)
                scale_factor = self.weights_config.get("scale_factor", 1)
                edge.weight_mob.scale(scale_factor)

    def create_weight(self, weight: float):
        weight_config = {**WEIGHT_CONFIG, **self.weights_config}
        label_fill_color = weight_config.pop("label_fill_color", WEIGHT_LABEL_FONT_COLOR)
        return LabeledDot(
            label=MathTex(weight, fill_color=label_fill_color), **weight_config)

    def create_edge(self, edge_type, u, v):
        """Create an edge mobject between two vertices."""
        edge_start = self[u] if isinstance(self[u], Node) else self[u].get_center()
        edge_end = self[v] if isinstance(self[v], Node) else self[v].get_center()
        if self.graph_type == GraphType.UNDIRECTED:
            edge_mobject = edge_type(edge_start, edge_end, z_index=-1, **self._edge_config[(u, v)])
        elif edge_type == Edge and self._edge_config[(u, v)].get("edge_type", None) == ArcBetweenPoints:
            edge_len = np.linalg.norm(self[u].get_center() - self[v].get_center()
                                      ) - (self[v].width + self[u].width) / 2
            edge_mobject = edge_type(edge_start, edge_end, z_index=-1, **self._edge_config[(u, v)])
            reference_line = Line(ORIGIN, [edge_len, 0, 0])
            reference_line.next_to(self[u], RIGHT, buff=0)
            u_v_angle = np.arctan2(self[v].get_center()[1] - self[u].get_center()[1],
                                   self[v].get_center()[0] - self[u].get_center()[0])
            if isinstance(edge_mobject, Edge) and edge_mobject.weight_mob is not None:
                edge_mobject.remove(edge_mobject.weight_mob)
            reference_line.rotate(u_v_angle, about_point=self[u].get_center())
            edge_mobject.put_start_and_end_on(reference_line.get_start(), reference_line.get_end())
            if isinstance(edge_mobject, Edge) and edge_mobject.weight_mob is not None:
                edge_mobject.add(edge_mobject.weight_mob)
                edge_mobject.update_weight(edge_mobject)
        else:
            edge_len = np.linalg.norm(self[u].get_center() - self[v].get_center()
                                      ) - (self[v].width + self[u].width) / 2
            edge_mobject = edge_type(edge_start, edge_end, z_index=-1, **self._edge_config[(u, v)])
            edge_mobject.put_start_and_end_on(ORIGIN, [edge_len, 0, 0])
            edge_mobject.next_to(self[u], RIGHT, buff=0)
            u_v_angle = np.arctan2(self[v].get_center()[1] - self[u].get_center()[1],
                                   self[v].get_center()[0] - self[u].get_center()[0])
            if isinstance(edge_mobject, Edge) and edge_mobject.weight_mob is not None:
                edge_mobject.remove(edge_mobject.weight_mob)
            edge_mobject.rotate(u_v_angle, about_point=self[u].get_center())
            if isinstance(edge_mobject, Edge) and edge_mobject.weight_mob is not None:
                edge_mobject.add(edge_mobject.weight_mob)
                edge_mobject.update_weight(edge_mobject)

        return edge_mobject

    def update_edges(self, graph):
        for (u, v), edge in graph.edges.items():
            edge_type = type(edge)
            tip = edge.pop_tips()

            new_edge = self.create_edge(edge_type, u, v)
            if isinstance(edge, Edge) and new_edge.weight_mob is not None:
                new_edge.weight_mob.match_height(edge.weight_mob)

            edge.become(new_edge)
            if len(tip) > 0:
                edge.add_tip(tip[0])

            edge.set_color(edge.get_color())
