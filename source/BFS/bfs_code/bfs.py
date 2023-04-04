from tools.consts import *
from tools.funcs import *
from tools.tmpGraph import GenericGraph, DiGraph
from pathlib import Path
from bfs_tools import *
from manim_editor import PresentationSectionType as pst
from typing import Callable, Iterable, List, Optional, Sequence, Union, Hashable

MAIN_PATH = Path(__file__).resolve().parent.parent
sys.path.append(str(MAIN_PATH.parent.parent))

PRESENTATION_MODE = False
DISABLE_CACHING = False
config.background_color = BACKGROUND_COLOR

# --------------------------------- constants --------------------------------- #
VERTEX_COLOR = DARK_BLUE
VERTEX_STROKE_WIDTH = DEFAULT_STROKE_WIDTH * 1.6
VERTEX_STROKE_COLOR = BLUE_D
VERTEX_LABEL_SCALE = 0.7
VERTEX_CONFIG = {"fill_color": VERTEX_COLOR, "stroke_color": VERTEX_STROKE_COLOR, "stroke_width": VERTEX_STROKE_WIDTH}

EDGE_COLOR = GREY
EDGE_STROKE_WIDTH = DEFAULT_STROKE_WIDTH * 2
TIP_SIZE = DEFAULT_ARROW_TIP_LENGTH * 0.4
EDGE_CONFIG = {"tip_config": {"tip_length": 0}, "stroke_color": EDGE_COLOR, "stroke_width": EDGE_STROKE_WIDTH}

VISITED_COLOR = PURE_GREEN
VISITED_EDGE_WIDTH = EDGE_STROKE_WIDTH * 1.5
VISITED_VERTEX_WIDTH = VERTEX_STROKE_WIDTH * 1.8
VISITED_TIP_SIZE = TIP_SIZE * 2.1
LABEL_COLOR = WHITE

DISTANCE_LABEL_BUFFER = 0.02
DISTANCE_LABEL_SCALE = 0.7
DISTANCE_LABEL_COLOR = ORANGE

LINES_OPACITY = 0.5


# --------------------------------- BFS --------------------------------- #


def get_neighbors(graph: GenericGraph, vertex):
    return [neighbor for neighbor in graph.vertices if (vertex, neighbor) in graph.edges]


def create_dist_label(index, graph, label):
    label = Tex(label, color=DISTANCE_LABEL_COLOR, weight=BOLD)
    if label.width < label.height:
        label.scale_to_fit_height(graph[index].radius * DISTANCE_LABEL_SCALE)
    else:
        label.scale_to_fit_width(graph[index].radius * DISTANCE_LABEL_SCALE)
    return label.move_to(graph[index]).next_to(graph[index][1], RIGHT, buff=DISTANCE_LABEL_BUFFER)


class BFSScene(Scene):
    def __init__(self, vertices: list[Hashable], edges: list[tuple[Hashable, Hashable]], start_vertex=1,
                 directed_graph=False, vertices_locations=None, **kwargs):
        super().__init__(**kwargs)
        self.directed_graph = directed_graph
        self.vertices = vertices
        self.edges = edges
        self.start_vertex = start_vertex
        self.vertices_locations = vertices_locations
        self.graph = self.create_graph()
        self.rendered_code = self.create_code()
        self.queue_mob, self.u, self.pi = self.create_bfs_vars(self.rendered_code)
        self.dist_mob = VGroup(
            *([VMobject()] + [create_dist_label(i, self.graph, r"$\infty$") for i in self.vertices]))  # 1-indexed

    def my_next_section(self, name: str = "unnamed", type: str = pst.SUB_NORMAL, skip_animations: bool = False):
        if PRESENTATION_MODE:
            self.next_section(name, type, skip_animations)
        else:
            self.wait()

    def construct(self):
        self.my_next_section("BFS", pst.NORMAL)

        self.play(Write(self.rendered_code))
        self.play(Write(self.graph))

        self.animate_bfs()

        self.play(highlight_code_lines(self.rendered_code, indicate=False))
        # self.play(Unwrite(self.graph), Unwrite(self.dist_mob))
        self.play(Unwrite(VGroup(self.rendered_code, self.queue_mob, self.u, self.pi)))
        self.wait()

    def animate_bfs(self):
        """
        Animate BFS algorithm. We assume that the graph is connected.
        Else, we need to run BFS for each connected component.
        Each step of the algorithm is animated separately.
        Note: vertices are 1-indexed
        """
        graph, rendered_code, dist_mob = self.graph, self.rendered_code, self.dist_mob
        queue_mob, u, pi = self.queue_mob, self.u, self.pi

        queue = [self.start_vertex]
        self.my_next_section("Initialize queue", pst.SUB_NORMAL)
        self.highlight_and_indicate_code([2])
        self.play(queue_mob.draw_array())

        dist = [np.Inf] * (len(graph.vertices) + 1)
        self.my_next_section("Initialize dist", pst.SUB_NORMAL)
        self.highlight_and_indicate_code([3, 4])
        self.play(AnimationGroup(*[anim(dist_mob[i]) for i in range(1, len(dist_mob)) for anim in [Write, Flash]],
                                 lag_ratio=0.3))

        dist[self.start_vertex] = 0
        self.my_next_section("Init first vertex dist", pst.SUB_NORMAL)
        self.highlight_and_indicate_code([5])
        self.wait(0.2)
        self.play(self.change_dist(self.start_vertex, 0))

        parent = [None] * (len(graph.vertices) + 1)
        self.my_next_section("Init first vertex parent", pst.SUB_NORMAL)
        self.highlight_and_indicate_code([6])
        self.play(pi.draw_array())
        self.play(pi.at(0, "-"))

        while queue:
            self.highlight_and_indicate_code([8])
            # animate pop
            cur_vertex = queue.pop(0)
            if cur_vertex == self.start_vertex:
                self.play(Write(u))
            self.my_next_section(f"Pop vertex {cur_vertex} from queue", pst.SUB_NORMAL)
            self.highlight_and_indicate_code([9])
            if cur_vertex == self.start_vertex:
                self.visit_vertex_animation(graph, None, cur_vertex)
            pop_item = queue_mob.get_square(0)
            self.play(queue_mob.indicate_at(0))
            self.play(pop_item.animate.match_y(u))
            pop_animation = queue_mob.pop(0, shift=RIGHT).animations
            self.play(AnimationGroup(*pop_animation[1:]))

            for neighbor in get_neighbors(graph, cur_vertex):
                if dist[neighbor] != np.Inf:
                    continue
                # animate for neighbor v of u & dist[v] = ∞
                self.my_next_section("Visit neighbor", pst.SUB_NORMAL)
                self.highlight_and_indicate_code([10])
                self.my_next_section("Update visit", pst.SUB_NORMAL)
                self.visit_vertex_animation(graph, cur_vertex, neighbor)

                # animate queue.push(v)
                queue.append(neighbor)
                self.my_next_section(f"Add vertex {neighbor} to queue", pst.SUB_NORMAL)
                self.highlight_and_indicate_code([11])
                self.play(queue_mob.push(neighbor))

                # animate dist[v] = dist[u] + 1
                dist[neighbor] = dist[cur_vertex] + 1
                self.my_next_section(f"Set distance {dist[cur_vertex] + 1} to vertex {neighbor}", pst.SUB_NORMAL)
                self.highlight_and_indicate_code([12])
                self.my_next_section("Update dist", pst.SUB_NORMAL)
                self.play(self.change_dist(neighbor, dist[neighbor]))

                # animate π[v] ← u
                parent[neighbor] = cur_vertex
                self.my_next_section(f"Add parent {cur_vertex} to vertex {neighbor}", pst.SUB_NORMAL)
                self.highlight_and_indicate_code([13])
                self.my_next_section("Update parent", pst.SUB_NORMAL)
                self.play(pi.at(neighbor - 1, cur_vertex))

            self.play(pop_animation[0])

    def create_code(self):
        code = '''def BFS(G,s): 
    queue ← Build Queue({s})
    for all vertices u in V do:
        dist[u] ← ∞
    dist[s] ← 0
    π[s] ← None
             
    while queue ≠ ø do:
        u = queue.pop() 
        for neighbor v of u & dist[v] = ∞:
                queue.push(v)
                dist[v] = dist[u] + 1
                π[v] ← u'''
        Code.set_default(font="Consolas")
        rendered_code = Code(code=code, tab_width=3, background="window", language="Python", style="fruity").to_corner(
            LEFT + UP)
        rendered_code.scale_to_fit_width(config.frame_width * 0.5).to_corner(LEFT + UP)
        rendered_code.background_mobject[0].set_fill(color=BACKGROUND_COLOR)
        return rendered_code

    def create_graph(self):
        """
        Create graph and add labels to vertices,
        Note: vertices are 1-indexed
        """
        if not self.directed_graph:
            self.edges += [(v, u) for u, v in self.edges]

        edge_config = EDGE_CONFIG
        if self.directed_graph:
            edge_configs = {}
            for k, v in self.edges:
                if (v, k) in self.edges:
                    edge_configs[(k, v)] = EDGE_CONFIG
                else:
                    edge_configs[(k, v)] = EDGE_CONFIG
                    edge_configs[(k, v)]["tip_config"]["tip_length"] = TIP_SIZE
            edge_config = edge_configs

        graph = DiGraph(self.vertices, self.edges, layout="circular", layout_scale=1.5, labels=True,
                        label_fill_color=LABEL_COLOR, vertex_config=VERTEX_CONFIG, edge_config=edge_config)
        for i, vertex in enumerate(graph.vertices):
            if self.vertices_locations is not None:
                graph[vertex].move_to(self.vertices_locations[i])
            graph[vertex][1].scale(VERTEX_LABEL_SCALE)
        relative_scale = config.frame_width * 0.5 if graph.width > graph.height else config.frame_height * 0.7
        graph.scale_to_fit_width(relative_scale).move_to(ORIGIN).to_edge(RIGHT, buff=0.2)
        return graph

    def create_bfs_vars(self, rendered_code: Code) -> tuple[ArrayMob, Tex, ArrayMob]:
        scale = 1
        queue_mob = ArrayMob("queue:", self.start_vertex, name_scale=scale).next_to(rendered_code, DOWN,
                                                                                    buff=0.5).to_edge(LEFT)

        u = Tex("u:").scale_to_fit_height(queue_mob.height_ref).next_to(queue_mob, DOWN, buff=queue_mob.get_square(
            0).height * 0.8).align_to(queue_mob.array_name, RIGHT)
        pi = ArrayMob(r"$\pi$:", *[""] * len(self.vertices), name_scale=scale, show_labels=True, labels_pos=DOWN,
                      align_point=u.get_right() + 0.5 * DOWN * (queue_mob.obj_ref.get_bottom()[1] - u.get_top()[1]),
                      starting_index=1)
        return queue_mob, u, pi

    def visit_vertex_animation(self, graph: GenericGraph, parent, next_vertex):
        visited_mark = Circle(radius=graph[next_vertex].radius, fill_opacity=0, stroke_width=VISITED_VERTEX_WIDTH,
                              stroke_color=VISITED_COLOR).move_to(graph[next_vertex]).scale_to_fit_height(
            graph[next_vertex].height)
        if parent is not None:
            visited_mark.rotate(graph.edges[(parent, next_vertex)].get_angle() + PI)
            self.play(graph.animate.add_edges((parent, next_vertex),
                                              edge_config={"stroke_color": VISITED_COLOR,
                                                           "stroke_width": VISITED_EDGE_WIDTH,
                                                           "tip_config": {
                                                               "tip_length": VISITED_TIP_SIZE if self.directed_graph else 0}}))
        self.play(Create(visited_mark))

    def change_dist(self, index: int, new_dist: int) -> AnimationGroup:
        old_dist = self.dist_mob[index]
        new_dist_tex = create_dist_label(index, self.graph, str(new_dist))
        self.dist_mob[index] = new_dist_tex
        return AnimationGroup(Transform(old_dist, new_dist_tex), Flash(new_dist_tex), lag_ratio=0.5)

    def highlight_and_indicate_code(self, lines: list, **kwargs):
        highlight, indicate = highlight_code_lines(self.rendered_code, lines, **kwargs)
        self.play(highlight)
        self.play(indicate)


class BigGraphBFS(BFSScene):
    def __init__(self, **kwargs):
        vertices = list(range(1, 9))
        edges = [(1, 7), (1, 8), (2, 3), (2, 4), (2, 5),
                 (2, 8), (3, 4), (6, 1), (6, 2), (7, 2), (7, 4), (3, 6)]
        start_vertex = 1
        super().__init__(vertices, edges, start_vertex, **kwargs)
    # def construct(self):
    #     super().construct()


class SmallGraphBFS(BFSScene):
    def __init__(self, **kwargs):
        vertices = list(range(1, 4))
        edges = [(1, 2), (1, 3), (2, 3)]
        start_vertex = 1
        super().__init__(vertices, edges, start_vertex, **kwargs)
    # def construct(self):
    #     super().construct()


class DirectedGraphBFS(BFSScene):
    def __init__(self, **kwargs):
        vertices = list(range(1, 8))
        edges = [(1, 2), (1, 3),
                 (2, 3), (2, 4), (2, 5), (3, 6), (3, 7),
                 (5, 4), (5, 1), (6, 1), (6, 7)]
        start_vertex = 1
        vertices_locations = [UP * 2, LEFT + UP, RIGHT + UP, 1.5 * LEFT, 0.5 * LEFT, 0.5 * RIGHT, 1.5 * RIGHT]
        super().__init__(vertices, edges, start_vertex, vertices_locations=vertices_locations, directed_graph=True,
                         **kwargs)
    # def construct(self):
    #     super().construct()


class MovingDiGraph(Scene):
    def construct(self):
        vertices = list(range(1, 8))
        edges = [(1, 2), (1, 3),
                 (2, 3), (2, 4), (2, 5), (3, 6), (3, 7),
                 (5, 4), (5, 1), (6, 1), (6, 7)]
        start_vertex = 1
        vertices_locations = [UP * 2, LEFT + UP, RIGHT + UP, 1.5 * LEFT, 0.5 * LEFT, 0.5 * RIGHT, 1.5 * RIGHT]
        g = DiGraph(vertices, edges, layout_scale=1.5, layout="circular", labels=True,
                    label_fill_color=LABEL_COLOR, vertex_config=VERTEX_CONFIG, edge_config=EDGE_CONFIG)
        for i, vertex in enumerate(g.vertices):
            g[vertex].move_to(vertices_locations[i])
        g.scale(2)
        g.update_edges(g)
        self.add(g)
        self.play(g.animate.add_edges((2, 4), edge_config={"stroke_color": VISITED_COLOR,
                                                           "stroke_width": VISITED_EDGE_WIDTH,
                                                           "tip_config": {
                                                               "tip_length": VISITED_TIP_SIZE}}))
        self.wait()


if __name__ == "__main__":

    # scenes_lst = [BigGraphBFS]
    scenes_lst = [SmallGraphBFS]
    # scenes_lst = [DirectedGraphBFS]
    # scenes_lst = [MovingDiGraph]

    for scene in scenes_lst:
        quality = "fourk_quality" if PRESENTATION_MODE else "low_quality"

        with tempconfig({"quality": quality, "preview": True, "media_dir": MAIN_PATH / "media", "save_sections": True,
                         "disable_caching": DISABLE_CACHING}):
            scene().render()
