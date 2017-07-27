import zmq
import threading
import time
from .task import Task
import warnings


class ThreadLocalZMQSocketHolder(threading.local):
    """
    manages zmq sockets in thread local state
    in order to avoid memory barrier issues
    """
    __slots__ = 'ready', 'url'

    def _mq(self):
        if not self.ready:
            return
        try:
            return self._socket
        except AttributeError:
            socket = zmq.Context.instance().socket(zmq.REQ)
            socket.connect(self.url)
            socket.send_json({'event_name': 'ping'})
            resp = socket.recv_json()
            if resp['message'] != 'PONG':
                raise Exception('Riggerlib server not ready')
            self._socket = socket
            return socket

    def request(self, data):
        if self.ready:
            self._mq().send_json(data)
            return self._mq().recv_json()


class RiggerClient(object):
    """
    A RiggerClient object allows TCP interaction with a Rigger instance running the TCP server.
    It takes the hook fire information, serializes it to JSON format and passes it over the TCP
    connection.

    Args:
        address: The address of the Rigger TCP server.
        port: The port of the Rigger TCP server, usually 21212.
    """

    def __init__(self, address, port):
        self.address = address
        self.port = str(port)
        self._socket_holder = ThreadLocalZMQSocketHolder()
        self._socket_holder.ready = False
        self._socket_holder.url = 'tcp://{}:{}'.format(
            self.address, self.port)

    def _request(self, data):
        return self._socket_holder.request(data)

    @property
    def ready(self):
        return self._socket_holder.ready

    @ready.setter
    def ready(self, value):
        self._socket_holder.ready = True

    @property
    def zmq(self):
        warnings.warn(DeprecationWarning(
            "RiggerClient.zmq is deprecated,"
            " please stop using it,"
            " there is no replacement"))
        return self._socket_holder._mq()

    def fire_hook(self, hook_name, grab_result=False, wait_for_task=False, **kwargs):
        raw_data = {
            'event_name': 'fire_hook',
            'hook_name': hook_name,
            'grab_result': grab_result,
            'wait_for_task': wait_for_task,
            'data': kwargs
        }
        try:
            response = self._request(raw_data)
            if grab_result or wait_for_task:
                status = 0
                while status != Task.FINISHED:
                    time.sleep(0.1)
                    task = self.task_status(response['tid'], grab_result)
                    status = task["status"]
                self.task_delete(response['tid'])
                if grab_result:
                    return task["output"]
                else:
                    return True
            else:
                return None
        except Exception:
            return None

    def task_status(self, tid, grab_result):
        raw_data = {'event_name': 'task_check', 'tid': tid, 'grab_result': grab_result}
        try:
            return self._request(raw_data)
        except Exception:
            return None

    def task_delete(self, tid):
        raw_data = {'event_name': 'task_delete', 'tid': tid}
        try:
            return self._request(raw_data)
        except Exception:
            return None

    def terminate(self):
        try:
            self._request({'event_name': 'shutdown'})
            self.ready = False
            return None
        except Exception:
            return None
