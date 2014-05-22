from collections import defaultdict, Mapping
from multiprocessing.pool import ThreadPool
from funcsigs import signature
from functools import wraps
import hashlib
import sys
import time
import yaml


class _realempty():
    pass


class Rigger(object):
    def __init__(self, config_file):
        self.pre_callbacks = defaultdict(dict)
        self.post_callbacks = defaultdict(dict)
        self.plugins = {}
        self.config_file = config_file
        self.squash_exceptions = False

    def read_config(self, config_file):
        """
        Reads in the config file and parses the yaml data
        """
        try:
            with open(config_file, "r") as stream:
                data = yaml.load(stream)
        except IOError:
            print "!!! Configuration file could not be loaded...exiting"
            sys.exit(127)
        except Exception as e:
            print e
            print "!!! Error parsing Configuration file"
            sys.exit(127)
        self.config = data

    def parse_config(self):
        """
        Reads the config data and sets up values
        """
        self.read_config(self.config_file)
        self.setup_plugin_instances()

    def setup_plugin_instances(self):
        """
        Sets up instances into a dict called instances and instantiates each
        instance of the plugin.
        """
        self.instances = {}
        self._threaded = self.config.get("threaded", True)
        plugins = self.config.get("plugins", None)
        for ident, config in plugins.iteritems():
            self.setup_instance(ident, config)

    def setup_instance(self, ident, config):
        """
        Sets up a single instance
        """
        plugin_name = config.get('plugin', None)
        if plugin_name in self.plugins:
            obj = self.plugins[plugin_name]
            if obj:
                obj_instance = obj(ident, config)
                self.instances[ident] = RiggerPluginInstance(ident, obj_instance, config)
        else:
            msg = "Plugin [{}] was not found, "\
                  "disabling instance [{}]".format(plugin_name, ident)
            print msg

    def fire_hook(self, hook_name, **kwargs):
        """
        Takes a hook_name and a selection of kwargs and fires off the appropriate callbacks
        """
        kwargs_updates = {}
        globals_updates = {}
        kwargs.update({'config': self.config})

        #First fire off any pre-hook callbacks
        if self.pre_callbacks.get(hook_name):
            #print "Running pre hook callback for {}".format(hook_name)
            kwargs_updates, globals_updates = self.process_callbacks(
                self.pre_callbacks[hook_name].values(), kwargs)

        #Now we can update the kwargs passed to the real hook with the updates
        self.update(self.global_data, globals_updates)
        self.update(kwargs, kwargs_updates)

        #Now fire off each plugin hook
        event_hooks = []
        for instance_name, instance in self.instances.iteritems():
            callbacks = instance.obj.callbacks
            enabled = instance.data.get('enabled', None)
            if callbacks.get(hook_name) and enabled:
                cb = callbacks[hook_name]
                event_hooks.append(cb)
        kwargs_updates, globals_updates = self.process_callbacks(event_hooks, kwargs)

        #One more update for hte post_hook callback
        self.update(self.global_data, globals_updates)
        self.update(kwargs, kwargs_updates)

        #Finally any post-hook callbacks
        if self.post_callbacks.get(hook_name):
            #print "Running post hook callback for {}".format(hook_name)
            kwargs_updates, globals_updates = self.process_callbacks(
                self.post_callbacks[hook_name].values(), kwargs)
        self.update(self.global_data, globals_updates)

    def process_callbacks(self, callback_collection, kwargs):
        """
        Checks to ensure that all the keywords for the function
        are correct and builds a new kwargs dict with only those values
        to avoid Exceptions related to argnames
        """
        loc_collect = {}
        glo_collect = {}
        if self._threaded:
            results_list = []
            pool = ThreadPool(10)
        for cb in callback_collection:
            required_args = [sig for sig in cb['args'] if isinstance(cb['args'][sig].default, type)]
            missing = list(set(required_args).difference(set(self.global_data.keys()))
                           .difference(set(kwargs.keys())))
            if not missing:
                new_kwargs = self.build_kwargs(cb['args'], kwargs)
                if self._threaded:
                    results_list.append(pool.apply_async(cb['func'], [], new_kwargs))
                else:
                    obtain_result = self.handle_results(cb['func'], [], new_kwargs)
                    loc_collect, glo_collect = self.handle_collects(
                        obtain_result, loc_collect, glo_collect)
            else:
                raise Exception('Function {} is missing kwargs {}'
                                .format(cb['func'].__name__, missing))

        if self._threaded:
            pool.close()
            pool.join()
            for result in results_list:
                obtain_result = self.handle_results(result.get, [], {})
                loc_collect, glo_collect = self.handle_collects(
                    obtain_result, loc_collect, glo_collect)
        return loc_collect, glo_collect

    def handle_results(self, call, args, kwargs):
        try:
            obtain_result = call(*args, **kwargs)
        except:
            if self.squash_exceptions:
                obtain_result = None
                self.handle_failure(sys.exc_info())
            else:
                raise

        return obtain_result

    def handle_collects(self, result, loc_collect, glo_collect):
        if result:
            if result[0]:
                self.update(loc_collect, result[0])
            if result[1]:
                self.update(glo_collect, result[1])
        return loc_collect, glo_collect

    def build_kwargs(self, args, kwargs):
        """
        Builds a new kwargs from a list of allowed args
        """
        returned_args = {}
        returned_args.update({name: self.global_data[name] for name in args
                              if not isinstance(self.global_data.get(name,
                                                                     _realempty()), _realempty)})
        returned_args.update({name: kwargs[name] for name in args
                              if not isinstance(kwargs.get(name, _realempty()), _realempty)})
        return returned_args

    def register_hook_callback(self, hook_name=None, ctype="pre", callback=None, name=None):
        """
        Registers pre and post callbacks
        """
        if hook_name and callback:
            callback_instance = self.create_callback(callback)
            if not name:
                name = hashlib.sha1(
                    str(time.time()) + hook_name + str(callback_instance['args'])).hexdigest()
            if ctype == "pre":
                self.pre_callbacks[hook_name][name] = callback_instance
            elif ctype == "post":
                self.post_callbacks[hook_name][name] = callback_instance

    def unregister_hook_callback(self, hook_name, ctype, name):
        if ctype == "pre":
            del self.pre_callbacks[hook_name][name]
        elif ctype == "post":
            del self.post_callbacks[hook_name][name]

    def register_plugin(self, cls, plugin_name=None):
        if plugin_name in self.plugins:
            print "Plugin name already taken [{}]".format(plugin_name)
        elif plugin_name is None:
            print "Plugin name cannot be None"
        else:
            #print "Registering plugin {}".format(plugin_name)
            self.plugins[plugin_name] = cls

    def get_instance_obj(self, name):
        if name in self.instances:
            return self.instances[name].obj
        else:
            return None

    def get_instance_data(self, name):
        if name in self.instances:
            return self.instances[name].data
        else:
            return None

    def configure_plugin(self, name, *args, **kwargs):
        obj = self.get_instance_obj(name)
        if obj:
            obj.configure(*args, **kwargs)
        else:
            print "Instance: [{}] does not exist, is your configuration correct?".format(name)

    @staticmethod
    def create_callback(callback):
        params = signature(callback).parameters
        return {
            'func': callback,
            'args': params
        }

    def update(self, orig_dict, updates):
        """
        Update dict objects with merge.
        """
        for key, val in updates.iteritems():
            if isinstance(val, Mapping):
                orig_dict[key] = self.update(orig_dict.get(key, {}), val)
            elif isinstance(orig_dict, Mapping):
                orig_dict[key] = updates[key]
            else:
                orig_dict = {key: updates[key]}
        return orig_dict

    def handle_failure(self, exc):
        print exc


class RiggerPluginInstance(object):
    def __init__(self, ident, obj, data):
        """Instance of a plugin"""
        self.ident = ident
        self.obj = obj
        self.data = data


class RiggerBasePlugin(object):
    def __init__(self, ident, data):
        self.callbacks = {}
        self.ident = ident
        self.data = data
        self.plugin_initialize()
        self.configured = False

    @staticmethod
    def check_configured(func):
        @wraps(func)
        def inner(self, *args, **kwargs):
            if self.configured:
                return func(self, *args, **kwargs)
        # If python3.2, this should _could_ be removed
        inner.__wrapped__ = func
        return inner

    def register_plugin_hook(self, event, callback):
        """
        Registers a plugins callback with the associated event. Each event can only have one
        plugin callback.

        For example, register_plugin_hook('start_test', self.start_test). The function will
        receive one parameter, and that will be the context variable which is passed from the
        hook_fire.
        """
        self.callbacks[event] = Rigger.create_callback(callback)
