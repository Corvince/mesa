import itertools
import warnings
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    cast,
)

from mesa.agent import Agent

Coordinate = Tuple[int, int]
GridContent = List[Agent]

F = TypeVar("F", bound=Callable[..., Any])


def accept_tuple_argument(wrapped_function: F) -> F:
    """ Decorator to allow grid methods that take a list of (x, y) coord tuples
    to also handle a single position, by automatically wrapping tuple in
    single-item list rather than forcing user to do it.

    """

    def wrapper(*args: Any) -> Any:
        if isinstance(args[1], tuple) and len(args[1]) == 2:
            return wrapped_function(args[0], [args[1]])
        return wrapped_function(*args)

    return cast(F, wrapper)


class MultiGrid:
    """ Base class for a rectangular grid with square cells.

    Grid cells are indexed by [x][y], where [0][0] is assumed to be the
    bottom-left and [width-1][height-1] is the top-right. If a grid is
    toroidal, the top and bottom, and left and right, edges wrap to each other
    Each position of the grid is referred to by a (x, y) coordinate tuple.
    You may access the content of a single cell by calling Grid[x, y].

    Properties:
        width, height: The grid's width and height.
        torus: Boolean which determines whether to treat the grid as a torus.
        empties: List of currently empty cells.

    Methods:
        position_agent: Preferred function to initially place agents.
        place_agent: Positions an agent on the grid, and set its pos variable.
        move_agent: Moves an agent from its current to a new position.
        remove_agent: Remove an agent from the grid.
        get_neighbors: Returns the objects surrounding a given cell.
        get_neighborhood: Returns the cells surrounding a given cell.
        get_contents: Returns the contents of a list of cells.
        coord_iter: Returns cell contens and coordinates of all cells.
        torus_adj: Converts coordinates, handles torus looping.
        out_of_bounds: Determines whether position is off the grid.

    """

    def __init__(self, width: int, height: int, torus: bool) -> None:
        """ Create a new grid.

        Args:
            width, height: The width and height of the grid
            torus: Boolean whether the grid wraps or not.

        """
        self.height = height
        self.width = width
        self.torus = torus

        self._grid = []  # type: List[List[GridContent]]

        for _ in range(self.width):
            col = []  # type: List[GridContent]
            for _ in range(self.height):
                col.append([])
            self._grid.append(col)

        # Add all cells to the empties list.
        self._empties = set(itertools.product(range(self.width), range(self.height)))
        self._all_cells = frozenset(self._empties)

        # Neighborhood Cache
        self._neighborhood_cache: Dict[Any, List[Coordinate]] = dict()

    def __getitem__(self, pos: Coordinate) -> GridContent:
        """Access contents of a given position."""
        if isinstance(pos, int):
            warnings.warn(
                """Accesing the grid via `grid[x][y]` is depreciated.
                Use `grid[x, y]` instead."""
            )
            return self._grid[pos]
        x, y = pos
        return self._grid[x][y]

    def __setitem__(self, pos: Coordinate, agent: Agent) -> None:
        """Add agents to a position."""
        x, y = pos
        self._grid[x][y].append(agent)

    def __iter__(self) -> Iterator[GridContent]:
        """Iterate over all cells in the grid."""
        return itertools.chain.from_iterable(self._grid)

    def coord_iter(self) -> Iterator[Tuple[GridContent, int, int]]:
        """Iterate over all cell contents and coordinates. """
        for row in range(self.width):
            for col in range(self.height):
                yield self[row, col], row, col  # agent, x, y

    def torus_adj(self, pos: Coordinate) -> Coordinate:
        """Convert coordinates, handling torus looping."""
        if not self.out_of_bounds(pos):
            return pos
        if not self.torus:
            raise Exception("Point out of bounds, and space non-toroidal.")
        return pos[0] % self.width, pos[1] % self.height

    def out_of_bounds(self, pos: Coordinate) -> bool:
        """Determines whether position is off the grid."""
        return tuple(pos) not in self._all_cells

    def place_agent(self, agent: Agent, pos: Coordinate) -> Agent:
        """Position an agent on the grid, and set its pos variable."""
        x, y = pos
        self._grid[x][y].append(agent)
        self._empties.discard(pos)
        setattr(agent, "pos", pos)
        return agent

    def remove_agent(self, agent: Agent) -> Agent:
        """Remove the agent from the grid and set its pos variable to None."""
        x, y = getattr(agent, "pos")
        content = self._grid[x][y]
        content.remove(agent)
        if not content:
            self._empties.add((x, y))
        setattr(agent, "pos", None)
        return agent

    def move_agent(self, agent: Agent, pos: Coordinate) -> Agent:
        """
        Move an agent from its current position to a new position.

        Args:
            agent: Agent to move. Must have a valid pos attribute.
            pos: Tuple of new position to move the agent to.

        """
        pos = self.torus_adj(pos)
        self.remove_agent(agent)
        self.place_agent(agent, pos)
        return agent

    @accept_tuple_argument
    def get_contents(self, cell_list: Iterable[Coordinate]) -> List[GridContent]:
        """Return a list of the cell contents for a given cell list."""
        return [self[pos] for pos in cell_list if not self.is_cell_empty(pos)]

    def get_neighborhood(
        self,
        pos: Coordinate,
        moore: bool,
        include_center: bool = False,
        radius: int = 1,
    ) -> List[Coordinate]:
        """ Return a list of cells that are in the neighborhood of a
        certain point.

        Args:
            pos: Coordinate tuple for the neighborhood to get.
            moore: If True, return Moore neighborhood
                   (including diagonals)
                   If False, return Von Neumann neighborhood
                   (exclude diagonals)
            include_center: If True, return the (x, y) cell as well.
                            Otherwise, return surrounding cells only.
            radius: radius, in cells, of neighborhood to get.

        Returns:
            A list of coordinate tuples representing the neighborhood;
            With radius 1, at most 9 if Moore, 5 if Von Neumann (8 and 4
            if not including the center).

        """
        cache_key = (pos, moore, include_center, radius)
        neighborhood = self._neighborhood_cache.get(cache_key, None)
        if neighborhood is None:
            x, y = pos
            coordinates = set()  # type: Set[Coordinate]
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx == 0 and dy == 0 and not include_center:
                        continue
                    # Skip coordinates that are outside manhattan distance
                    if not moore and abs(dx) + abs(dy) > radius:
                        continue
                    # Skip if not a torus and new coords out of bounds.
                    coord = (x + dx, y + dy)

                    if self.out_of_bounds(coord):
                        if not self.torus:
                            continue
                        coord = self.torus_adj(coord)

                    if coord not in coordinates:
                        coordinates.add(coord)

            neighborhood = sorted(coordinates)
            self._neighborhood_cache[cache_key] = neighborhood
        return neighborhood

    def get_neighbors(
        self,
        pos: Coordinate,
        moore: bool = True,
        include_center: bool = False,
        radius: int = 1,
    ) -> List[Agent]:
        """ Return a list of neighbors to a certain point.

        Args:
            pos: Coordinate tuple for the neighborhood to get.
            moore: If True, return Moore neighborhood
                    (including diagonals)
                   If False, return Von Neumann neighborhood
                     (exclude diagonals)
            include_center: If True, return the (x, y) cell as well.
                            Otherwise,
                            return surrounding cells only.
            radius: radius, in cells, of neighborhood to get.

        Returns:
            A list of non-None objects in the given neighborhood;
            at most 9 if Moore, 5 if Von-Neumann
            (8 and 4 if not including the center).

        """
        neighborhood = self.get_neighborhood(pos, moore, include_center, radius)
        neighbors = self.get_contents(neighborhood)
        return list(itertools.chain.from_iterable(neighbors))

    def neighbor_iter(self, pos: Coordinate, moore: bool = True) -> Iterator[Agent]:
        """Depreciated."""
        yield from self.get_neighbors(pos, moore=moore)

    def iter_neighborhood(
        self,
        pos: Coordinate,
        moore: bool,
        include_center: bool = False,
        radius: int = 1,
    ) -> Iterator[Coordinate]:
        """Depreciated."""
        yield from self.get_neighborhood(pos, moore, include_center, radius)

    def iter_neighbors(
        self,
        pos: Coordinate,
        moore: bool,
        include_center: bool = False,
        radius: int = 1,
    ) -> Iterator[GridContent]:
        """Depreciated."""
        neighborhood = self.get_neighborhood(pos, moore, include_center, radius)
        yield from self.get_contents(neighborhood)

    @accept_tuple_argument
    def iter_cell_list_contents(
        self, cell_list: Iterable[Coordinate]
    ) -> Iterator[GridContent]:
        """Depreciated."""
        yield from self.get_contents(cell_list)

    @accept_tuple_argument
    def get_cell_list_contents(self, cell_list: Iterable[Coordinate]) -> List[Agent]:
        """Depreciated"""
        return list(itertools.chain(*self.get_contents(cell_list)))

    def is_cell_empty(self, pos: Coordinate) -> bool:
        """ Returns a bool of the contents of a cell. """
        return pos in self._empties

    def move_to_empty(self, agent: Agent) -> None:
        """ Moves agent to a random empty cell, vacating agent's old cell. """
        if len(self._empties) == 0:
            raise Exception("ERROR: No empty cells")
        new_pos = agent.random.choice(self.empties)
        self.move_agent(agent, new_pos)

    def find_empty(self) -> Optional[Coordinate]:
        """ Pick a random empty cell. """
        from warnings import warn
        import random

        warn(
            (
                "`find_empty` is being phased out since it uses the global "
                "`random` instead of the model-level random-number generator. "
                "Consider replacing it with having a model or agent object "
                "explicitly pick one of the grid's list of empty cells."
            ),
            DeprecationWarning,
        )

        if self.exists_empty_cells():
            return random.choice(self.empties)
        return None

    @property
    def empties(self) -> List[Coordinate]:
        return sorted(self._empties)

    @property
    def all_cells(self) -> List[Coordinate]:
        return sorted(self._all_cells)

    def exists_empty_cells(self) -> bool:
        """Depreciated.

        Test with `if grid.empties`
        """
        return len(self._empties) > 0


class SingleGrid(MultiGrid):
    """ Grid where each cell contains exactly at most one object. """

    def __init__(self, width: int, height: int, torus: bool) -> None:
        """ Create a new single-item grid.

        Args:
            width, height: The width and width of the grid
            torus: Boolean whether the grid wraps or not.

        """
        super().__init__(width, height, torus)

    def __getitem__(self, pos: Coordinate) -> Optional[Agent]:
        if isinstance(pos, int):
            warnings.warn("depreciated")
            return [content[0] for content in self._grid[pos] if content]
        x, y = pos
        content = self._grid[x][y]
        return content[0] if content else None

    def get_contents(self, cell_list: Iterable[Coordinate]) -> List[Agent]:
        return super().get_contents(cell_list)

    def position_agent(
        self, agent: Agent, x: Union[str, int] = "random", y: Union[str, int] = "random"
    ) -> None:
        """ Position an agent on the grid.
        This is used when first placing agents! Use 'move_to_empty()'
        when you want agents to jump to an empty cell.
        Use 'swap_pos()' to swap agents positions.
        If x or y are positive, they are used, but if "random",
        we get a random position.
        Ensure this random position is not occupied (in Grid).

        """
        # TODO: Allow to use only one random value
        if x == "random" or y == "random":
            if len(self._empties) == 0:
                raise Exception("ERROR: Grid full")
            coords: Tuple[int, int] = agent.random.choice(self.empties)
        else:
            coords = (int(x), int(y))
        agent.pos = coords
        self.place_agent(agent, coords)

    def place_agent(self, agent: Agent, pos: Coordinate) -> Agent:
        if not self.is_cell_empty(pos):
            raise Exception("Cell not empty")
        return super().place_agent(agent, pos)

    def get_neighbors(
        self,
        pos: Coordinate,
        moore: bool = True,
        include_center: bool = False,
        radius: int = 1,
    ) -> List[Agent]:
        """ Return a list of neighbors to a certain point.

        Args:
            pos: Coordinate tuple for the neighborhood to get.
            moore: If True, return Moore neighborhood
                    (including diagonals)
                   If False, return Von Neumann neighborhood
                     (exclude diagonals)
            include_center: If True, return the (x, y) cell as well.
                            Otherwise,
                            return surrounding cells only.
            radius: radius, in cells, of neighborhood to get.

        Returns:
            A list of non-None objects in the given neighborhood;
            at most 9 if Moore, 5 if Von-Neumann
            (8 and 4 if not including the center).

        """
        neighborhood = self.get_neighborhood(pos, moore, include_center, radius)
        return self.get_contents(neighborhood)
        # return list(itertools.chain.from_iterable(neighbors))

    @accept_tuple_argument
    def get_cell_list_contents(self, cell_list: Iterable[Coordinate]) -> List[Agent]:
        return self.get_contents(cell_list)


class Grid(SingleGrid):
    """ Grid where each cell can contain more than one object.

    Grid cells are indexed by [x][y], where [0][0] is assumed to be at
    bottom-left and [width-1][height-1] is the top-right. If a grid is
    toroidal, the top and bottom, and left and right, edges wrap to each other.

    Each grid cell holds a set object.

    Properties:
        width, height: The grid's width and height.

        torus: Boolean which determines whether to treat the grid as a torus.

        grid: Internal list-of-lists which holds the grid cells themselves.

    Methods:
        get_neighbors: Returns the objects surrounding a given cell.
    """

    def place_agent(self, agent: Agent, pos: Coordinate) -> Agent:
        if not self.is_cell_empty(pos):
            x, y = pos
            self._grid[x][y].clear()
            self._empties.add(pos)
        return super().place_agent(agent, pos)
