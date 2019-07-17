# -*- coding: utf-8 -*-
"""
ModularServer
=============

A visualization server which renders a model via one or more elements.

The concept for the modular visualization server as follows:
A visualization is composed of VisualizationElements, each of which defines how
to generate some visualization from a model instance and render it on the
client. VisualizationElements may be anything from a simple text display to
a multilayered HTML5 canvas.

The actual server is launched with one or more VisualizationElements;
it runs the model object through each of them, generating data to be sent to
the client. The client page is also generated based on the JavaScript code
provided by each element.

This file consists of the following classes:

VisualizationElement: Parent class for all other visualization elements, with
                      the minimal necessary options.
PageHandler: The handler for the visualization page, generated from a template
             and built from the various visualization elements.
SocketHandler: Handles the websocket connection between the client page and
                the server.
ModularServer: The overall visualization application class which stores and
               controls the model and visualization instance.


ModularServer should *not* need to be subclassed on a model-by-model basis; it
should be primarily a pass-through for VisualizationElement subclasses, which
define the actual visualization specifics.

For example, suppose we have created two visualization elements for our model,
called canvasvis and graphvis; we would launch a server with:

    server = ModularServer(MyModel, [canvasvis, graphvis], name="My Model")
    server.launch()

The client keeps track of what step it is showing. Clicking the Step button in
the browser sends a message requesting the viz_state corresponding to the next
step position, which is then sent back to the client via the websocket.

The websocket protocol is as follows:
Each message is a JSON object, with a "type" property which defines the rest of
the structure.

Server -> Client:
    Send over the model state to visualize.
    Model state is a list, with each element corresponding to a div; each div
    is expected to have a render function associated with it, which knows how
    to render that particular data. The example below includes two elements:
    the first is data for a CanvasGrid, the second for a raw text display.

    {
    "type": "viz_state",
    "data": [{0:[ {"Shape": "circle", "x": 0, "y": 0, "r": 0.5,
                "Color": "#AAAAAA", "Filled": "true", "Layer": 0,
                "text": 'A', "text_color": "white" }]},
            "Shape Count: 1"]
    }

    Informs the client that the model is over.
    {"type": "end"}

    Informs the client of the current model's parameters
    {
    "type": "model_params",
    "params": 'dict' of model params, (i.e. {arg_1: val_1, ...})
    }

Client -> Server:
    Reset the model.
    TODO: Allow this to come with parameters
    {
    "type": "reset"
    }

    Get a given state.
    {
    "type": "get_step",
    "step:" index of the step to get.
    }

    Submit model parameter updates
    {
    "type": "submit_params",
    "param": name of model parameter
    "value": new value for 'param'
    }

    Get the model's parameters
    {
    "type": "get_params"
    }

"""
import copy
import os
import pickle
import webbrowser

from typing import Optional

import tornado.autoreload
import tornado.escape
import tornado.gen
import tornado.ioloop
import tornado.web
import tornado.websocket

from mesa.visualization.UserParam import UserSettableParameter

# Suppress several pylint warnings for this file.
# Attributes being defined outside of init is a Tornado feature.
# pylint: disable=attribute-defined-outside-init


# =============================================================================
# Actual Tornado code starts here:


class PageHandler(tornado.web.RequestHandler):
    """ Handler for the HTML template which holds the visualization. """

    def get(self):
        self.render(
            "vega_template.html",
            port=self.application.port,
            model_name=self.application.model_name,
            description=self.application.description,
        )


class SocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        self.set_nodelay(True)
        self.states = []
        if self.application.verbose:
            print("Socket opened!")

        self.write_message(
            {
                "type": "vega_specs",
                "data": self.application.vega_specifications,
                "n_sims": self.application.n_simulations,
            }
        )

    def on_message(self, message):
        """ Receiving a message from the websocket, parse, and act accordingly.

        """
        msg = tornado.escape.json_decode(message)
        if self.application.verbose:
            print(msg)

        try:
            response_function = getattr(self, msg["type"])
            response_function(**msg["data"])
        except AttributeError:
            if self.application.verbose:
                print("Unexpected message!")

    @property
    def current_state(self):
        return {
            "type": "model_state",
            "data": [model.as_json() for model in self.application.models],
        }

    def get_state(self, step):
        self.write_message(self.states[step])

    def submit_params(self, param, value):
        """Submit model parameters."""

        # Is the param editable?
        if param in [param["parameter"] for param in self.application.user_params]:
            if isinstance(self.application.model_kwargs[param], UserSettableParameter):
                self.application.model_kwargs[param].value = value
            else:
                self.application.model_kwargs[param] = value

    def reset(self):
        self.application.reset_models()
        self.states = []
        self.write_message(
            {"type": "model_params", "params": self.application.user_params}
        )
        self.states.append(self.current_state)
        self.application.step()

    def step(self, step):
        if step < self.application.current_step:
            self.application.restore_state(max(step - 1, 0))
            self.states = self.states[: step - 1]
            self.states.append(self.current_state)
            self.application.step()

        elif step > self.application.current_step:
            self.application.step()

        self.states.append(self.current_state)
        self.application.step()

    def call_method(self, step, model_id, data):
        if self.application.current_step != step:
            self.application.restore_state(step)
        self.states = self.states[:step]

        model = self.application.models[model_id]
        try:
            method = getattr(model, "on_click")
            method(**data)
        except (AttributeError, TypeError):
            pass

        self.states.append(self.current_state)


class VegaServer(tornado.web.Application):
    """ Main visualization application. """

    verbose = True

    port = 8521  # Default port to listen on
    max_steps = 100000

    # Handlers and other globals:
    page_handler = (r"/", PageHandler)
    socket_handler = (r"/ws", SocketHandler)
    static_handler = (
        r"/templates/(.*)",
        tornado.web.StaticFileHandler,
        {"path": os.path.dirname(__file__) + "/templates"},
    )

    handlers = [page_handler, socket_handler, static_handler]

    settings = {
        "debug": True,
        "template_path": os.path.dirname(__file__) + "/templates",
    }

    EXCLUDE_LIST = ("width", "height")

    def __init__(
        self,
        model_cls,
        vega_specifications: str,
        name: str = "Mesa Model",
        model_params: Optional[dict] = None,
        n_simulations: int = 1,
    ):
        """ Create a new visualization server with the given elements. """
        # Prep visualization elements:
        self.vega_specifications = vega_specifications

        # Initializing the model
        self.model_name = name
        self.model_cls = model_cls
        self.description = "No description available"
        if hasattr(model_cls, "description"):
            self.description = model_cls.description
        elif model_cls.__doc__ is not None:
            self.description = model_cls.__doc__

        self.n_simulations = n_simulations

        if model_params is None:
            model_params = {}

        self.model_params = model_params

        self.model_kwargs = [
            copy.deepcopy(self.model_params) for _ in range(n_simulations)
        ]
        self.reset_models()

        # Initializing the application itself:
        super().__init__(self.handlers, **self.settings)

    @property
    def user_params(self):
        result = []
        for param, val in self.model_params.items():
            if isinstance(val, UserSettableParameter):
                val.parameter = param
                result.append(val.json)
        return result

    def step(self):
        """Advance all models by one step.
        """
        self.pickles[self.current_step] = pickle.dumps(self.models)
        for model in self.models:
            model.step()
        self.current_step += 1

    def restore_state(self, step: int):
        self.models = pickle.loads(self.pickles[step])
        self.current_step = step

    def reset_models(self):
        """ Reinstantiate the model object, using the current parameters. """

        self.models = []
        self.pickles = {}
        for i in range(self.n_simulations):
            model_params = {}
            for key, val in self.model_kwargs[i].items():
                if isinstance(val, UserSettableParameter):
                    if (
                        val.param_type == "static_text"
                    ):  # static_text is never used for setting params
                        continue
                    model_params[key] = val.value
                else:
                    model_params[key] = val
            self.models.append(self.model_cls(**model_params))
            self.current_step = 0

    def launch(self, port=None):
        """ Run the app. """
        if port is not None:
            self.port = port
        url = "http://127.0.0.1:{PORT}".format(PORT=self.port)
        print("Interface starting at {url}".format(url=url))
        self.listen(self.port)
        webbrowser.open(url)
        tornado.autoreload.start()
        tornado.ioloop.IOLoop.current().start()
