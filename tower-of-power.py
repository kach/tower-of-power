# This is a bit of an experiment, really: a way to generate "box tower"
# dependency diagrams in the style of the inside cover of Matt Parker's book,
# "Things to Make and Do in the Fourth Dimension." Parker's blocks represent
# prerequisite-knowledge dependencies between his book chapters, but surely the
# same idea could apply to all sorts of dependencies: software modules and
# college course prereqs come to mind as examples.

# After struggling for a few hours with trying to generate such diagrams
# directly, I eventually gave up and wrote a solver-aided program. Hence, this
# program depends on the z3 solver and its Python interface (neither of which
# is hard to install).

import z3

# ...but I'm getting ahead of myself. Really, the story of "how do I draw
# dependency diagrams" begins with the question, "what are dependencies?"
# I think of dependencies as directed acyclic graphs, or DAGs. Each
# chapter/module/course is a node, and edge from A to B indicates that "A
# depends on B." The reason the graph is acyclic should then be clear: A and B
# can't depend on each other!

# There's actually a lot of literature on drawing diagrams of directed acyclic
# graphs, some of which can be found in the `graphviz' documentation (the
# working title to this program was `Sugiyama's Last Stand').

# For now, though, here's a small DAG class in Python to get started.

class DAGException(Exception):
    pass

class dag():

# "root" is a placeholder node: anything with no dependencies secretly depends
# on "root". Why? Because all the blocks at the base of the tower need to sit
# on the same ground level. "root" is the floor.

    ROOT = '( root )'

    def __init__(self):
        self.deps = {}                 # maps a node to a list of its dependencies
        self.clss = {dag.ROOT: 'base'} # maps a node to its CSS class
        self.text = {dag.ROOT: ''}     # maps a node to its label text
        self.dep_cache = {}            # this speeds up some algorithms below
        self.insert(dag.ROOT, [])

# The following incomprehensible regular expressions define the BOX file format
# which I invented to make it easier to specify DAGs for this project.

    def load_line(self, line):
        import re
        wsop_re = r'\s*'
        name_re = r'([\w-]+)'
        deps_re = r'\((\s*(?:[\w-]+(?:\s*,\s*[\w-]+)*)?\s*)\)'
        clss_re = r'(?:\.([\w-]+))?'
        text_re = r':\s*(.*)?'

        line_re = re.compile(
            wsop_re + name_re +
            wsop_re + deps_re +
            wsop_re + clss_re +
            wsop_re + text_re
        )
        match = line_re.match(line)
        if match:
            name = match.group(1)
            deps = match.group(2).replace(',', ' ').split()
            clss = match.group(3) or 'box-generic'
            text = match.group(4)
            if len(deps) == 0:
                deps = [dag.ROOT]
            self.insert(name, deps)
            self.clss[name] = clss
            self.text[name] = text
        elif len(line.split()) == 0 or line[0] == '#':
            pass
        else:
            raise DAGException("Syntax error on line: `" + line + "`")

    def load_file(self, text):
        lines = text.split('\n')
        for line in lines:
            self.load_line(line)



# A lot of the invariants on this DAG are maintained by complaining loudly as
# soon as they are violated. So, you have to insert nodes in the correct order.
# Other than that, this insertion routine is unexciting.

    def insert(self, name, deps):
        if name in self.get_nodes():
            raise DAGException("Already added this name to DAG.")
        for d in deps:
            if d not in self.deps:
                raise DAGException("Unknown dependency: %s (for %s)"%(d, name))
        self.deps[name] = list(deps)

# This is also unexciting.

    def get_nodes(self):
        return self.deps.keys()

# This, however, is kind of interesting. Notice that Parker's tower doesn't
# distinguish between "direct dependencies" and "transitive dependencies": if
# A depends on B and C, and B itself depends on C, then the box for A doesn't
# need to sit on the boxes for both B and C (in fact, it can't!). The correct
# drawing is "A on B, B on C", with the understanding that A "of course"
# depends on C as well.
#
# The following predicates sort out this mess, by giving me a way to check if a
# dependency is "direct" or "transitive" in that sense. Transitive dependencies
# can be ignored.

    def get_dependencies(self, node):
        return self.deps[node]

    def is_dependency(self, node, dep):
        if (node, dep) in self.dep_cache:
            return self.dep_cache[(node, dep)]
        shallow_deps = self.get_dependencies(node)
        if dep in shallow_deps:
            self.dep_cache[(node, dep)] = True
            return True
        for sd in shallow_deps:
            if self.is_dependency(sd, dep):
                self.dep_cache[(node, dep)] = True
                return True
        self.dep_cache[(node, dep)] = False
        return False

    def is_transitive_dependency(self, node, dep):
        for sd in self.get_dependencies(node):
            if self.is_dependency(sd, dep):
                return True
        return False

    def is_direct_dependency(self, node, dep):
        return self.is_dependency(node, dep) and\
            not self.is_transitive_dependency(node, dep)

# Okay, okay, fine, I'll start talking about the solver now.

    def solve(self):

# The way it works is, each box is represented by four symbolic integers,
# representing the X/Y coordinates of its top-left and bottom-right vertices.

# (Note, however, that because computers are silly, the Y coordinates DECREASE
# as you go UP the tower. Just something to keep in mind. Otherwise we get
# upside-down stalactite-towers.)

        svs = {}
        solver = z3.Solver()
        for node in self.get_nodes():
            svs[node] = (
                (z3.Int(node+'_x0'), z3.Int(node+'_y0')),
                (z3.Int(node+'_x1'), z3.Int(node+'_y1'))
            )

# Almost immediately, we need to make some sanity assertions. We want the
# top-left corner to actually be "to the left" and "on top of" the bottom-right
# corner, so we have to tell the solver that.

            solver.add(svs[node][0][0] < svs[node][1][0])
            solver.add(svs[node][0][1] < svs[node][1][1])

# There's also a bit of logic here to automatically make boxes taller if they
# have a lot of text, so that text doesn't overflow awkwardly. This is janky,
# but it works!

            solver.add(
                svs[node][1][1] - svs[node][0][1] >=\
                (len(self.text[node].split('\\')) - len(self.text[node].split('\\')) / 2)
            )

# And finally, we enforce that everything happens in the first quadrant.

            solver.add(svs[node][0][0] >= 0)

# Now we can put root (recall, the "ground") literally on the ground!

        solver.add(svs[dag.ROOT][0][0] == 0)
        solver.add(svs[dag.ROOT][0][1] == 0)


# Up next, we enforce that no boxes intersect. This is done by checking if the
# X and Y ranges are disjoint (at least one needs to be -- but not necessarily
# both!).

        def ranges_disjoint(x0min, x0max, x1min, x1max):
            return z3.Or(x0min >= x1max, x0max <= x1min)

        for node1 in self.get_nodes():
            for node2 in self.get_nodes():
                if node1 != node2:
                    solver.add(
                        z3.Or(
                            ranges_disjoint(
                                svs[node1][0][0],
                                svs[node1][1][0],
                                svs[node2][0][0],
                                svs[node2][1][0]
                            ),
                            ranges_disjoint(
                                svs[node1][0][1],
                                svs[node1][1][1],
                                svs[node2][0][1],
                                svs[node2][1][1]
                            )
                        )
                    )

# This is the hard one: for each pair of nodes, it creates an "A is on top of
# B" assertion, and then asserts either it or its negation, depending on
# whether or not B is a direct dependency of A.

        for node in self.get_nodes():
            for dep in self.get_nodes():
                on_top = z3.And(

# When is "A" on top of "B"? There are two conditions:

# First, A's box's floor is directly on B's box's ceiling.

                    svs[node][1][1] == svs[dep][0][1],

# Second, the boxes have intersecting X ranges.

                    z3.Not(
                        ranges_disjoint(
                            svs[node][0][0], svs[node][1][0],
                            svs[dep] [0][0], svs[dep] [1][0]
                        )
                    )
                )
                if self.is_direct_dependency(node, dep):
                    solver.add(on_top)
                else:
                    solver.add(z3.Not(on_top))
        
# Finally, for the sake of ~aesthetics~, there's a bit of logic to
# automatically minimize the total perimeter of all the blocks. (Why not area,
# you ask? Because area is nonlinear and the solver takes *much* longer to work
# with such constrants!)

        def perimeter(node):
            return (svs[node][1][0] - svs[node][0][0]) + (svs[node][1][1] - svs[node][0][1])
        total_perim = sum([perimeter(node) for node in self.get_nodes()])

# (That's what the loop is for: it keeps asking the solver to "do better" until
# the solver can't do any better and gives up. It may or may not be a metaphor
# for life.)

        rects = None
        perim_tgt = len(self.get_nodes()) * 4 * 3
        while True:
            perim_tgt -= 1
            solver.add(total_perim < perim_tgt)
            check = solver.check()
            if check == z3.sat:
                model = solver.model()

                rects = []

# I translate the solver output into SVG coordinates using some hardcoded
# scaling factors and randomized fudge factors.

                for node in self.get_nodes():
                    x0 = model.eval(svs[node][0][0])
                    y0 = model.eval(svs[node][0][1])
                    x1 = model.eval(svs[node][1][0])
                    y1 = model.eval(svs[node][1][1])

                    import random
                    x0 = int(str(x0)) * 160 + 10 + random.choice(range(10))
                    y0 = int(str(y0)) * 50
                    x1 = int(str(x1)) * 160 - 10 + random.choice(range(10))
                    y1 = int(str(y1)) * 50

                    rects.append((node, x0, y0, x1, y1))

# This is the "solver gives up" case

            else:
                return rects

# This is perhaps the least exciting bit of the whole program: just some silly
# SVG generation routines. There's some logic to get the text wrapping to work,
# but other than that, it's pretty simple (and by "simple" I mean
# "extensible"!).

    def render(self, rects, css):
        min_x = min([x0 for node, x0, y0, x1, y1 in rects]) - 5
        max_x = max([x1 for node, x0, y0, x1, y1 in rects]) + 5
        min_y = min([y0 for node, x0, y0, x1, y1 in rects]) - 5
        max_y = max([y1 for node, x0, y0, x1, y1 in rects]) + 5
        width = max_x - min_x
        height = max_y - min_y

        out = ""
        out += """<svg viewBox="%d %d %d %d" xmlns="http://www.w3.org/2000/svg">""" % (min_x, min_y, width, height)
        out += """
        <style>
        rect {
            stroke: hsl(0, 100%, 80%);
            fill: hsl(0, 100%, 90%);
        }
        rect.red {
            stroke: hsl(0, 100%, 80%);
            fill: hsl(0, 100%, 90%);
        }
        rect.yellow {
            stroke: hsl(60, 100%, 80%);
            fill: hsl(60, 100%, 90%);
        }
        rect.green {
            stroke: hsl(120, 100%, 80%);
            fill: hsl(120, 100%, 90%);
        }
        rect.blue {
            stroke: hsl(180, 100%, 80%);
            fill: hsl(180, 100%, 90%);
        }
        rect.purple {
            stroke: hsl(240, 100%, 80%);
            fill: hsl(240, 100%, 90%);
        }
        rect.pink {
            stroke: hsl(300, 100%, 80%);
            fill: hsl(300, 100%, 90%);
        }

        rect.base {
            stroke: hsl(60, 100%, 80%);
            fill: hsl(60, 100%, 90%);
        }
        text {
            font-family: Garamond, sans-serif;
            font-size: 14pt;
        }
        """ + css + """
        </style>
        """

        for (node, x0, y0, x1, y1) in rects:
            out += """  <rect fill="white" stroke="gray" x="%d" y="%d" width="%d" height="%d" rx="4" ry="4" class="%s"></rect>"""%(
                x0, y0,
                x1 - x0, y1 - y0 - 1,
                self.clss.get(node, 'box-generic')
            )
        for (node, x0, y0, x1, y1) in rects:
            out += """  <text x="%d" y="%d" width="100" class="%s">%s</text>"""%(
                x0 + 4, y0,
                self.clss.get(node, 'box-generic'),
                ''.join(["""<tspan x="%d" dy="%d">%s</tspan>"""%(x0 + 4, 20, text) for i, text in enumerate(self.text.get(node, node).split('\\'))])
            )

        out += """</svg>"""
        return out


# And that's it! The rest is just a tiny command-line interface that reads a
# BOX file (with optional CSS) and outputs the SVG rendering.

import sys

d = dag()
d.load_file(open(sys.argv[1]).read())

css = ''
if len(sys.argv) == 3:
    with open(sys.argv[2], 'r') as cssf:
        css = cssf.read()

rects = d.solve()
if rects is not None:
    print d.render(rects, css)
else:
    print "You seem to be in dependency hell."
