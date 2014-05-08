from collections import defaultdict
from multiprocessing.pool import ThreadPool
from funcsigs import signature
import hashlib
import sys
import time
import yaml


class Rigger(object):
    def __init__(self, config_file):
        self.pre_callbacks = defaultdict(dict)
        self.post_callbacks = defaultdict(dict)
        self.plugins = {}
        self.config_file = config_file

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
        plugins = self.config.get("plugins", None)
        for ident, config in plugins.iteritems():
            if config.get('enabled', None):
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
        Fires a specific hook and gives context data
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
        self.global_data.update(globals_updates)
        kwargs.update(kwargs_updates)

        #Now fire off each plugin hook
        event_hooks = []
        for instance_name, instance in self.instances.iteritems():
            callbacks = instance.obj.callbacks
            if callbacks.get(hook_name):
                cb = callbacks[hook_name]
                event_hooks.append(cb)
        kwargs_updates, globals_updates = self.process_callbacks(event_hooks, kwargs)

        #One more update for hte post_hook callback
        self.global_data.update(globals_updates)
        kwargs.update(kwargs_updates)

        #Finally any post-hook callbacks
        if self.post_callbacks.get(hook_name):
            #print "Running post hook callback for {}".format(hook_name)
            self.process_callbacks(self.post_callbacks[hook_name].values(), kwargs)

    def process_callbacks(self, callback_collection, kwargs):
        """
        Checks to ensure that all the keywords for the function
        are correct and builds a new kwargs dict with only those values
        to avoid Exceptions related to argnames
        """
        local_collect_dict = {}
        global_collect_dict = {}
        results_list = []
        pool = ThreadPool(10)
        for cb in callback_collection:
            missing = list(set(cb['args']).difference(set(self.global_data.keys()))
                           .difference(set(kwargs.keys())))
            if not missing:
                new_kwargs = self.build_kwargs(cb['args'], kwargs)
                results_list.append(pool.apply_async(cb['func'], [], new_kwargs))
            else:
                raise Exception('Function {} is missing kwargs {}'
                                .format(cb['func'].__name__, missing))
        pool.close()
        pool.join()
        for result in results_list:
            obtain_result = result.get()
            if obtain_result:
                if obtain_result[0]:
                    local_collect_dict.update(obtain_result[0])
                if obtain_result[1]:
                    global_collect_dict.update(obtain_result[1])
        return local_collect_dict, global_collect_dict

    def build_kwargs(self, args, kwargs):
        """
        Builds a new kwargs from a list of allowed args
        """
        returned_args = {}
        returned_args.update({name: self.global_data[name] for name in args
                              if self.global_data.get(name, None)})
        returned_args.update({name: kwargs[name] for name in args if kwargs.get(name, None)})
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

    def get_instance(self, name):
        if name in self.instances:
            return self.instances[name].obj
        else:
            return None

    @staticmethod
    def create_callback(callback):
        return {
            'func': callback,
            'args': signature(callback).parameters.keys()
        }


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

    def register_plugin_hook(self, event, callback):
        """
        Registers a plugins callback with the associated event. Each event can only have one
        plugin callback.

        For example, register_plugin_hook('start_test', self.start_test). The function will
        receive one parameter, and that will be the context variable which is passed from the
        hook_fire.
        """
        self.callbacks[event] = Rigger.create_callback(callback)
