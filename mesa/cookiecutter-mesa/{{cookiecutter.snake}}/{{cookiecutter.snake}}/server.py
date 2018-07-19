"""
Configure visualization elements and instantiate a server
"""

from .model import {{cookiecutter.model}}, {{cookiecutter.agent}}  # noqa

from mesa.visualization.ModularVisualization import ModularServer
from mesa.visualization.modules import CanvasGrid, ChartModule
from mesa.visualization.UserParam import UserSettableParameter


def circle_portrayal_example(agent):
    if agent is None:
        return

    portrayal = {"Shape": "circle",
                 "Filled": "true",
                 "Layer": 0,
                 "r": 0.5,
                 "Color": "Pink"}
    return portrayal


canvas_element = CanvasGrid(circle_portrayal_example, 20, 20, 500, 500)
chart_element = ChartModule([{"Label": "agents",
                              "Color": "Pink"}])

model_kwargs = {"num_agents": UserSettableParameter(
                    'slider',
                    "Number of agents", 10, 1, 100, 1,
                    description="Choose the number of agents"),
                "width": 20,
                "height": 20}

server = ModularServer({{cookiecutter.model}},
                       [canvas_element, chart_element],  # noqa
                       "{{cookiecutter.camel}}", model_kwargs)
