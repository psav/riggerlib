from __future__ import print_function
from .server import Rigger
from functools import wraps


class RiggerBasePlugin(object):
    def __init__(self, ident, data, _rigger_instance):
        self.callbacks = {}
        self.ident = ident
        self.data = data
        self.plugin_initialize()
        self.configured = False
        self._rigger_instance = _rigger_instance

    @staticmethod
    def check_configured(func):
        """Checks if a plugin is configured before proceeding"""
        @wraps(func)
        def inner(self, *args, **kwargs):
            if self.configured:
                return func(self, *args, **kwargs)
        # If python3.2, this should _could_ be removed
        inner.__wrapped__ = func
        return inner

    def register_plugin_hook(self, event, callback=None, bg=False):
        """
        Registers a plugins callback with the associated event. Each event can only have one
        plugin callback.

        For example, register_plugin_hook('start_test', self.start_test). The function will
        receive one parameter, and that will be the context variable which is passed from the
        hook_fire. Or you can omit the callback parameter, it will then infer the callback method
        is called the same as the event.
        """
        if callback is None:
            callback = getattr(self, event)
        self.callbacks[event] = Rigger.create_callback(callback)

    def fire_hook(self, hook_name, **kwargs):
        if 'grab_result' in kwargs:
            self._rigger_instance.log_message('ERROR: Cannot grab result of a nested hook')
            kwargs.pop('grab_result')
        self._rigger_instance.fire_hook(hook_name, **kwargs)
