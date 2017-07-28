
import riggerlib
import pytest


@pytest.mark.parametrize('name', [
    'Rigger',
    'RiggerClient',
    'RiggerBasePlugin',
    'recursive_update',
])
def test_exported_names(name):
    getattr(riggerlib, name)