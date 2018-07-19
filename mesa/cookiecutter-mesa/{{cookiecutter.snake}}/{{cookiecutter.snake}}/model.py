import random

from mesa import Agent, Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from mesa.datacollection import DataCollector


class {{cookiecutter.agent}}(Agent):  # noqa
    """
    An agent
    """

    def __init__(self, unique_id, model):
        """
        Customize the agent
        """
        self.unique_id = unique_id
        super().__init__(unique_id, model)

    def step(self):
        """
        Modify this method to change what an individual agent will do during
        each step.
        Can include logic based on other agents.
        """
        pass


class {{cookiecutter.model}}(Model):
    """
    The model class holds the model-level attributes, manages the agents,
    and generally handles the global level of our model.

    Currently, there are three model-level parameters:
        num_agents: How many agents the model contains
        width, height: The grid size of the model space

    When we start the model, we want it to populate a grid with the given
    number of agents.

    The scheduler is a special model component which controls the order in
    which agents are activated.
    """

    def __init__(self, num_agents, width, height):
        super().__init__()
        self.num_agents = num_agents
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(width=width, height=height, torus=True)

        for i in range(self.num_agents):
            agent = {{cookiecutter.agent}}(unique_id=i, model=self)
            self.schedule.add(agent)

            x = random.randrange(self.grid.width)
            y = random.randrange(self.grid.height)
            self.grid.place_agent(agent, (x, y))

        # Data collector
        self.datacollector = DataCollector(
            {"agents": "num_agents"}
        )

        # Start the model in a running state and collect initial data
        self.running = True
        self.datacollector.collect(self)

    def step(self):
        """
        A model step. Used for advancing the schedule and collecting data
        """
        self.schedule.step()
        self.datacollector.collect(self)
