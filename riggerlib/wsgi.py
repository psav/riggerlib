import flask
import zmq
from gunicorn.app.base import BaseApplication

application = flask.Flask('riggerlib')

_zmq_socket = None
_zmq_socket_address = None


@application.before_first_request
def setup_zmq_socket():
    global _zmq_socket
    if _zmq_socket is None:
        ctx = zmq.Context()
        _zmq_socket = ctx.socket(zmq.REQ)
        _zmq_socket.connect(_zmq_socket_address)
    # fire off a message before serving requests
    # (or rather, don't start if communication with rigger is busted)
    zmq_communicate('ping')


@application.route('/terminate/', methods=['GET', 'POST'])
def terminate():
    zmq_communicate('shutdown')
    flask.abort('503')


@application.route('/fire_hook/', methods=['GET', 'POST'])
def fire_unnamed_hook():
    json_dict = flask.request.get_json(force=True)
    return zmq_communicate('fire_hook', **json_dict)


@application.route('/task_check/', methods=['GET', 'POST'])
def task_check():
    json_dict = flask.request.get_json(force=True)
    return zmq_communicate('task_check', tid=json_dict['tid'])


class RiggerServer(BaseApplication):
    """embedded rigger server, powered by gunicorns

    based on https://gunicorn-docs.readthedocs.org/en/latest/custom.html

    """
    def __init__(self, options=None):
        self.options = options or {}
        super(RiggerServer, self).__init__()

    def load_config(self):
        # update the gunicorn cfg with passed-in options
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self):
        return application


def server_runner(zmq_socket_address, options=None, **option_kwargs):
    global _zmq_socket_address
    _zmq_socket_address = zmq_socket_address
    # options can come in as a dict or kwargs
    options = options or {}
    options.update(option_kwargs)
    # Intended to be run in its own process, so make sure the args are basic types
    return RiggerServer(options).run()


def zmq_communicate(event_name, **extra):
    json_dict = {'event_name': event_name}
    json_dict.update(extra)
    _zmq_socket.send_json(json_dict)
    response = _zmq_socket.recv_json()
    message = response['message']

    # handle special cases immediately
    # otherwise return the complete
    if message == 'OK':
        response = flask.jsonify(response)
    elif message == 'NOT FOUND':
        response = flask.abort(404)
    elif message == 'PONG':
        # not intended to be used in a flask view
        response = None
    else:
        # bad request
        response = flask.abort(400)
    return response
