import zmq
import threading
import time
from .task import Task


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
        self.ctx = zmq.Context()
        self._zmq_socket = None
        self.ready = False
        self._lock = threading.Lock()

    def _request(self, data):
        with self._lock:
            self.zmq.send_json(data)
            return self.zmq.recv_json()

    @property
    def zmq(self):
        if self.ready:
            if not self._zmq_socket:
                self._zmq_socket = self.ctx.socket(zmq.REQ)
                self._zmq_socket.connect('tcp://{}:{}'.format(self.address, self.port))
                self._zmq_socket.send_json({'event_name': 'ping'})
                resp = self._zmq_socket.recv_json()
                if resp['message'] != 'PONG':
                    del self._zmq_socket
                    raise Exception('Riggerlib server not ready')
            return self._zmq_socket
        else:
            return None

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
