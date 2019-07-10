var define = window.hybrids.define
var html = window.hybrids.html
var parent = window.hybrids.parent
var property = window.hybrids.property

// import { html, define, parent } from "https://unpkg.com/hybrids/src"

/**
 * Main AppStore for saving state across the Application
 * @typedef {Object} AppStore
 * @property {number} steps - The current model step
 * @property {boolean} running - Should the model continously update
 * @property {boolean} done - Whether the model is in a running state
 * @property {Parameter[]} parameter - User-settable parameters
 * @property {boolean} rendered - Is the current visualization state rendered
 * @property {number} timeout - the current timeout for step changes
 */
const AppStore = {
  steps: { observe: sendStep },
  running: false,
  done: false,
  parameter: {
    ...property([]),
    observe: sendParameter
  },
  fps: 3,
  timeout: 0
}

/**
 * Control section to start/step/reset the model
 * @typedef {object} AppControl
 * @property {AppStore} store - element instance of the AppStore
 * @property {boolean} isRunning - Is the model in a running state
 * @property {string} labelStartStop - The label for the start/stop button
 * @property {string} render - How the three buttons appear
 */
const AppControl = {
  store: parent(AppStore),
  isRunning: ({ store }) => store.running,
  labelStartStop: ({ isRunning }) => (isRunning ? "Stop" : "Start"),
  render: ({ isRunning, labelStartStop }) => html`
    <wl-button onclick=${toggleRunning}>${labelStartStop}</wl-button>
    ${isRunning
      ? html`
          <wl-button disabled onclick=${incrementStep}> Step</wl-button>
        `
      : html`
          <wl-button onclick=${incrementStep}> Step</wl-button>
        `}
    <wl-button onclick=${resetModel}>Reset</wl-button>
  `
}

/**
 * Input section for the individual Input Parameters
 * @typedef {object} InputParameters
 * @property {string[]} parameter - List of parameter names
 * @property {string} render - Mapping of names to mesa inputs
 */
const InputParameters = {
  store: parent(AppStore),
  parameter: ({ store }) => Object.keys(store.parameter),
  render: ({ parameter }) => html`
    <h2>Input Parameters</h2>
    ${parameter.map(
      param => html`
        <mesa-input paramName=${param}></mesa-input>
      `
    )}
  `
}

/**
 * @typedef {object} MesaInput
 * @property {AppStore} store - app-store element instance
 * @property {string} paramName - name of the parameter
 * @property {Parameter} parameter - user-settable input parameter
 */
const MesaInput = {
  store: parent(AppStore),
  paramName: "",
  parameter: ({ store, paramName }) => store.parameter[paramName],
  render: ({ parameter }) => html`
    <wl-expansion>
      <span slot="title">${parameter.options.name}</span>
      <span slot="description">${parameter.currentValue}</span>
      ${addInput(parameter)}
    </wl-expansion>
  `
}

/**
 * Create input elements based on the type of the input parameter
 * @param {Parameter} parameter - Input parameter
 */
function addInput(parameter) {
  let type = parameter.type
  let options = parameter.options
  let currentValue = parameter.currentValue
  switch (type) {
    case "slider":
      return html`
        <wl-slider
          thumbLabel
          min=${options.min_value}
          max=${options.max_value}
          step=${options.step}
          buffervalue=${currentValue}
          oninput=${changeValue}
          label=${options.value}
        >
          <span slot="before">${options.min_value}</span>
          <span slot="after">${options.max_value}</span>
        </wl-slider>
      `
    case "number":
      return html`
        <wl-textfield
          type="number"
          min=${options.min_value}
          max=${options.max_value}
          step=${options.step}
          value=${options.value}
          oninput=${changeValue}
        ></wl-textfield>
      `
    case "choice":
      return html`
        <wl-select oninput=${changeValue}>
          ${options.choices.map(
            option =>
              html`
                <option>${option}</option>
              `
          )}
        </wl-select>
      `
    case "checkbox":
      return html`
        ${options.value
          ? html`
              <wl-switch checked></wl-switch>
            `
          : html`
              <wl-switch></wl-switch>
            `}
      `
    case "static_text":
      return html`
        <wl-text>${options.value}</wl-text>
      `

    default:
      console.log("Unexpected parameter type:")
      console.log(type)
  }
}

/**
 * @typedef {object} FPSControl
 * @property {number} currentStep - The current model step
 * @property {number} fps - the current frames per second
 * @property {string} render - Display of current step and slider for FPS control
 */
const FPSControl = {
  store: parent(AppStore),
  currentStep: ({ store }) => (store.steps < 0 ? 0 : store.steps),
  fps: ({ store }) => store.fps,
  render: ({ currentStep, fps }) => html`
    <style>
      wl-text {
        margin-left: 8px;
      }
      :host {
        display: flex;
        align-items: center;
      }
    </style>
    <wl-slider
      min="0"
      max="25"
      step="1"
      value=${fps}
      oninput=${updateFPS}
      label="FPS Control"
      thumbLabel
    >
    </wl-slider>
    <wl-text slot="left">Current Step: ${currentStep}</wl-text>
  `
}

define("app-store", AppStore)
define("app-control", AppControl)
define("input-parameters", InputParameters)
define("mesa-input", MesaInput)
define("fps-control", FPSControl)

/**
 * Host element instance connected to an AppStore.
 * @typedef {Object} Host
 * @property {AppStore} store - The main application store

/**
 * Increment model steps by one.
 * @param {Host} host - an element instance
 */
function incrementStep({ store }) {
  if (!store.done) {
    store.steps += 1
  }
}

/**
 * Toggle the models running state.
 * @param {Host} host - an element instance
 */
function toggleRunning({ store }) {
  clearTimeout(store.timeout)
  if (!store.done) {
    store.running = !store.running
  }
  if (store.running) {
    incrementStep({ store: store })
  }
}

/**
 * Reset the model
 * @param {Host} host - an element instance
 */
function resetModel({ store }) {
  clearTimeout(store.timeout)
  store.done = false
  store.steps = -1
}

/**
 * Change input parameter value in the store
 * @param {InputElement} host - mesa-input instance
 * @param {Event} event - input event
 */
function changeValue({ store, paramName }, event) {
  store.parameter = {
    ...store.parameter,
    [paramName]: {
      ...store.parameter[paramName],
      options: {
        ...store.parameter[paramName].options,
        value: event.target.value
      }
    }
  }
}

function updateFPS({ store }, { target }) {
  store.fps = target.value
}

// Side effect functions below

// Set-up element container, reference to app store instance and legacy control object
const vizElements = []
const store = document.querySelector("app-store")
const control = { tick: store.steps }

/**
 * React to changes in the step counter - by resetting or getting the next step.
 * @param {AppStore} store - The application store
 */
function sendStep(store) {
  if (store.steps < 0) {
    send({ type: "reset" })
    store.timeout = setTimeout(incrementStep, 1, {
      store: store
    })
  } else {
    send({ type: "get_step", step: store.steps })
  }
}

/**
 * Add user-settable parameters to the input section.
 * @param {AppStore} store - element instance of the app store
 * @param {Parameter} param - raw parameter input from the Model Server
 */
function addParameter(store, param) {
  store.parameter = {
    ...store.parameter,
    [param.parameter]: {
      currentValue: param.value,
      type: param.param_type,
      options: param
    }
  }
}

/**
 * Check which values have changed and send them to the model server
 * @param {AppStore} store - store element instance
 * @param {Parameter[]} value - new values of the parameters
 * @param {Parameter[]} lastValue - old values of the parameters
 */
function sendParameter(store, value, lastValue = []) {
  Object.keys(lastValue).forEach(param => {
    if (value[param].options.value != lastValue[param].options.value) {
      send({
        type: "submit_params",
        param: param,
        value: Number(value[param].options.value) || value[param].options.value
      })
    }
  })
}

/** Open the websocket connection; support TLS-specific URLs when appropriate */
const ws = new window.WebSocket(
  (window.location.protocol === "https:" ? "wss://" : "ws://") +
    window.location.host +
    "/ws"
)

/**
 * Get the first step once the websocket is open (via resetting the model)
 */
ws.onopen = () => (store.steps = -1)

/**
 * Parse and handle an incoming message on the WebSocket connection.
 * @param {string} message - the message received from the WebSocket
 */
ws.onmessage = function(message) {
  const msg = JSON.parse(message.data)
  switch (msg.type) {
    case "viz_state":
      // Update visualization state
      control.tick = store.steps
      vizElements.forEach((element, index) => element.render(msg.data[index]))
      if (store.running) {
        store.timeout = setTimeout(incrementStep, 1000 / store.fps, {
          store: store
        })
      }
      break
    case "end":
      // We have reached the end of the model
      store.done = true
      store.running = false
      break
    case "reset":
      vizElements.forEach(element => element.reset())
      break
    case "model_params":
      // Create input elements for each model parameter
      msg.params.forEach(param => addParameter(store, param))
      break
    default:
      // There shouldn't be any other message
      console.log("Unexpected message.")
      console.log(msg)
  }
}

/**
 * Turn an object into a string to send to the server, and send it.
 * @param {string} message - The message to send to the Python server
 */
function send(message) {
  const msg = JSON.stringify(message)
  ws.send(msg)
}

window.store = document.querySelector("app-store")
window.control = control
window.elements = vizElements
