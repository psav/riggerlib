from collections import defaultdict, Mapping
from multiprocessing.pool import ThreadPool
from funcsigs import signature
from functools import wraps
import hashlib
import sys
import time
import yaml


class _realempty():
    """ A dummy class to be able to differentiate between None and "Really None". """
    pass


class Rigger(object):
    """ A Rigger event framework instance.

    The Rigger object holds all configuration and instances of plugins. By default Rigger accepts
    a configuration file name to parse, though it is perfectly acceptable to pass the configuration
    into the ``self.config`` attribute.

    Args:
        config_file: A configuration file holding all of Riggers base and plugin configuration.
    """
    def __init__(self, config_file):
        self.pre_callbacks = defaultdict(dict)
        self.post_callbacks = defaultdict(dict)
        self.plugins = {}
        self.config_file = config_file
        self.squash_exceptions = False
        self.initialized = False

    def read_config(self, config_file):
        """
        Reads in the config file and parses the yaml data.

        Args:
            config_file: A configuration file holding all of Riggers base and plugin configuration.

        Raises:
            IOError: If the file can not be read.
            Exception: If there is any error parsing the configuration file.
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
        Takes the configuration data from ``self.config`` and sets up the plugin instances.
        """
        self.read_config(self.config_file)
        self.setup_plugin_instances()

    def setup_plugin_instances(self):
        """
        Sets up instances into a dict called ``self.instances`` and instantiates each
        instance of the plugin. It also sets the ``self._threaded`` option to determine
        if plugins will be processed synchronously or asynchronously.
        """
        self.instances = {}
        self._threaded = self.config.get("threaded", False)
        plugins = self.config.get("plugins", {})
        for ident, config in plugins.iteritems():
            self.setup_instance(ident, config)

    def setup_instance(self, ident, config):
        """
        Sets up a single instance into the ``self.instances`` dict. If the instance does
        not exist, a warning is printed out.

        Args:
            ident: A plugin instance identifier.
            config: Configuration dict from the yaml.
        """
        plugin_name = config.get('plugin', {})
        if plugin_name in self.plugins:
            obj = self.plugins[plugin_name]
            if obj:
                obj_instance = obj(ident, config)
                self.instances[ident] = RiggerPluginInstance(ident, obj_instance, config)
        else:
            msg = "Plugin [{}] was not found, "\
                  "disabling instance [{}]".format(plugin_name, ident)
            self.log_message(msg)

    def fire_hook(self, hook_name, **kwargs):
        """
        Takes a hook_name and a selection of kwargs and fires off the appropriate callbacks.

        This function is the guts of Rigger and is responsible for running the callback and
        hook functions. It first loads some blank dicts to collect the updates for the local
        and global namespaces. After this, it loads the pre_callback functions along with
        the kwargs into the callback collector processor.

        The return values are then classifed into local and global dicts and updates proceed.
        After this, the plugin hooks themselves are then run using the same methodology. Their
        return values are merged with the existing dicts and then the same process happens
        for the post_callbacks.

        Args:
            hook_name: The name of the hook to fire.
            kwargs: The kwargs to pass to the hooks.
        """
        if not self.initialized:
            return
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
        Processes a collection of callbacks or hooks for a particular event, namely pre, hook or
        post.

        The functions are passed in as an array to ``callback_collection`` and process callbacks
        first iterates each function and ensures that each one has the correct arguments available
        to it. If not, an Exception is raised. Then, depending on whether Threading is enabled or
        not, the functions are either run sequentially, or loaded into a ThreadPool and executed
        asynchronously.

        The returned local and global updates are either collected and processed sequentially, as
        in the case of the non-threaded behaviour, or collected at the end of the
        callback_collection processing and handled there.

        Note:
            It is impossible to predict the order of the functions being run. If the order is
            important, it is advised to create a second event hook that will be fired before the
            other. Rigger has no concept of hook or callback order and is unlikely to ever have.

        Args:
            callback_collection: A list of functions to call.
            kwargs: A set of kwargs to pass to the functions.

        Returns: A tuple of local and global namespace updates.
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
        """
        Handles results and depending on configuration, squashes exceptions and logs or
        returns the obtained result.

        Args:
            call: The function call.
            args: The positional arguments.
            kwargs: The keyword arguments.

        Returns: The obtained result of the callback or hook.
        """
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
        """
        Handles extracting the information from the hook/callback result.

        If the hook/callback returns None, then the dicts are returned unaltered, else
        they are updated with local, global namespace updates.

        Args:
            result: The result to process.
            loc_collect: The local namespace updates collection.
            glo_collect: The global namespace updates collection.
        Returns: A tuple containing the local and global updates.
        """
        if result:
            if result[0]:
                self.update(loc_collect, result[0])
            if result[1]:
                self.update(glo_collect, result[1])
        return loc_collect, glo_collect

    def build_kwargs(self, args, kwargs):
        """
        Builds a new kwargs from a list of allowed args.

        Functions only receive a single set of kwargs, and so the global and local namespaces
        have to be collapsed. In this way, the local overrides the global namespace, hence if
        a key exists in both local and global, the local value will be passed to the function
        under the the key name and the global value will be forgotten.

        The args parameter ensures that only the expected arguments are supplied.

        Args:
            args: A list of allowed argument names
            kwargs: A dict of kwargs from the local namespace.
        Returns: A consolidated global/local namespace with local overrides.
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
        Registers pre and post callbacks.

        Takes a callback function and assigns it to the hook_name with an optional identifier.
        The optional identifier makes it possible to hot bind functions into hooks and to
        remove them at a later date with ``unregister_hook_callback``.

        Args:
            hook_name: The name of the event hook to respond to.
            ctype: The call back type, either ``pre`` or ``post``.
            callback: The callback function.
            name: An optional name for the callback instance binding.
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
        """
        Unregisters a pre or post callback.

        If the binding has a known name, this function allows the removal of a binding.

        Args:
            hook_name: The event hook name.
            ctype: The callback type, either ``pre`` or ``post``.
            name: An optional name for the callback instance binding.
        """
        if ctype == "pre":
            del self.pre_callbacks[hook_name][name]
        elif ctype == "post":
            del self.post_callbacks[hook_name][name]

    def register_plugin(self, cls, plugin_name=None):
        """ Registers a plugin class to a name.

        Multiple instances of the same plugin can be used in Rigger, ``self.plugins``
        stores un-initialized class defintions to be used by ``setup_instances``.

        Args:
            cls: The class.
            plugin_name: The name of the plugin.
        """
        if plugin_name in self.plugins:
            print "Plugin name already taken [{}]".format(plugin_name)
        elif plugin_name is None:
            print "Plugin name cannot be None"
        else:
            #print "Registering plugin {}".format(plugin_name)
            self.plugins[plugin_name] = cls

    def get_instance_obj(self, name):
        """
        Gets the instance object for a given ident name.

        Args:
            name: The ident name of the instance.
        Returns: The object of the instance.
        """
        if name in self.instances:
            return self.instances[name].obj
        else:
            return None

    def get_instance_data(self, name):
        """
        Gets the instance data(config) for a given ident name.

        Args:
            name: The ident name of the instance.
        Returns: The data(config) of the instance.
        """
        if name in self.instances:
            return self.instances[name].data
        else:
            return None

    def configure_plugin(self, name, *args, **kwargs):
        """
        Attempts to configure an instance, passing it the args and kwargs.

        Args:
            name: The ident name of the instance.
            args: The positional args.
            kwargs: The keyword arguments.
        """
        obj = self.get_instance_obj(name)
        if obj:
            obj.configure(*args, **kwargs)
        else:
            print "Instance: [{}] does not exist, is your configuration correct?".format(name)

    @staticmethod
    def create_callback(callback):
        """
        Simple function to inspect a function and return it along with it param names wrapped
        up in a nice dict. This forms a callback object.

        Args:
            callback: The callback function.
        Returns: A dict of function and param names.
        """
        params = signature(callback).parameters
        return {
            'func': callback,
            'args': params
        }

    def update(self, orig_dict, updates):
        """
        Update dict objects with recursive merge.

        Args:
            orig_dict: The original dict.
            updates: The updates to merge with the dictionary.
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
        """
        Handles an exception. It is expected that this be overidden.
        """
        self.log_message(exc)

    def log_message(self, message):
        """
        "Logs" a message. It is expected that this be overidden.
        """
        print message


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
        """Checks if a plugin is configured before proceeding"""
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
