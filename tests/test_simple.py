import pytest
from riggerlib import Rigger, RiggerClient
from riggerlib.plugins import test
from time import sleep

base_config = {
    'squash_exceptions': True,
    'threaded': False,
    'server_address': '127.0.0.1',
    'server_port': 21234,
    'server_enabled': True,
    'plugins': {
        'test': {
            'enabled': True,
            'plugin': 'test'
        }
    }
}


@pytest.yield_fixture
def riggerlib_client():
    rig = Rigger(None)
    rig.config = base_config
    rig.config['zmq_socket_address'] = 'tcp://127.0.0.1:{}'.format(21235)
    rig.register_plugin(test.Test, 'test')
    rig.setup_plugin_instances()
    rig.start_server()
    rig.global_data = {'test': dict()}
    rig.initialized = True
    sleep(3)
    rig_client = RiggerClient('127.0.0.1', 21234)
    yield rig_client
    rig_client.terminate()


def test_simple_connection(riggerlib_client):
    res = riggerlib_client.fire_hook('start_test', test_name='name',
        test_location='location', grab_result=True)
    assert res.get('test', {}).get('start', {})
    res = riggerlib_client.fire_hook('finish_test', test_name='name',
        test_location='location', grab_result=True)
    assert res.get('test', {}).get('finish', {})
