from riggerlib.client import ThreadLocalZMQSocketHolder
import threading
import zmq


def pong_responder(url, times):
    socket = zmq.Context.instance().socket(zmq.REP)
    socket.bind(url)
    for _ in range(times):
        socket.recv()  # ignore data
        socket.send(b'{"message": "PONG"}')


def test_sockt_holder_thread_gets_different_socket():

    holder = ThreadLocalZMQSocketHolder()
    holder.url = "inproc://test-socket-holder"
    holder.ready = True
    sockets = []

    def target():
        with holder.mq() as socket:
            sockets.append(socket)

    t = threading.Thread(target=target)
    t.start()

    responder = threading.Thread(
        target=pong_responder,
        kwargs={'url': holder.url, 'times': 2})
    responder.start()

    t.join()
    with holder.mq() as socket:
        assert sockets[0] is not socket
    responder.join()
