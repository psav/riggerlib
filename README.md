Rigger
======

Introduction
------------
Rigger is an event handling framwork. It allows for an arbitrary number of plugins to be
setup to respond to events, with a namspacing system to allow data to be passed to and from
these plugins. It is extensible and customizable enough that it can be used for a variety of
purposes.

Plugins
-------
The main guts of Rigger is around the plugins. Before Rigger can do anything it must have
a configured plugin. This plugin is then configured to bind certain functions inside itself
to certain events. When Rigger is triggered to handle a certain event, it will tell the plugin
that that particular event has happened and the plugin will respond accordingly.

In addition to the plugins, Rigger can also run certain callback functions before and after
the hook function itself. These are call pre and post hook callbacks. Rigger allows multiple
pre and post hook callbacks to be defined per event, but does not guarantee the order that they
are executed in.

Let's take the example of using the unit testing suite py.test as an example for Rigger.
Suppose we have a number of tests that run as part of a test suite and we wish to store a text
file that holds the time the test was run and its result. This information is required to reside
in a folder that is relevant to the test itself. This type of job is what Rigger was designed
for.

To begin with, we need to create a plugin for Rigger. Consider the following piece of code::

    from artifactor import RiggerBasePlugin
    import time


    class Test(RiggerBasePlugin):

        def plugin_initialize(self):
            self.register_plugin_hook('start_test', self.start_test)
            self.register_plugin_hook('finish_test', self.finish_test)

        def start_test(self, test_name, test_location, artifact_path):
            filename = artifact_path + "-" + self.ident + ".log"
            with open(filename, "w") as f:
                f.write(test_name + "\n")
                f.write(str(time.time()) + "\n")

        def finish_test(self, test_name, artifact_path, test_result):
            filename = artifact_path + "-" + self.ident + ".log"
            with open(filename, "w+") as f:
                f.write(test_result)

This is a typical plugin in Rigger, it consists of 2 things. The first item is
the special function called ``plugin_initialize()``. This is important
and is equivilent to the ``__init__()`` that would usually be found in a class definition.
Rigger calls ``plugin_initialize()`` for each plugin as it loads it.
Inside this section we register the hook functions to their associated events. Each event
can only have a single function associated with it. Event names are able to be freely assigned
so you can customize plugins to work to specific events for your use case.
The ``register_plugin_hook()`` takes an event name as a string and a function to callback when
that event is experienced.

Next we have the hook functions themselves, ``start_test()`` and ``finish_test()``. These
have arguments in their prototypes and these arguments are supplied by Rigger and are
created either as arguments to the ``fire_hook()`` function, which is responsible for actually
telling Rigger that an even has occured, or they are created in the pre hook script.

Local and Global Namespaces
---------------------------
To allow data to be passed to and from hooks, Rigger has the idea of global and event local
namespaces. The global values persist in the Rigger instance for its lifetime, but the event local
values are destroyed at the end of each event.

Rigger uses the global and local values referenced earlier to store these argument values.
When a pre, post or hook callback finishes, it has the opportunity to supply updates to both
the global and local values dictionaries. In doing this, a pre-hook script can prepare data,
which will could be stored in the locals dictionary and then passed to the actual plugin hook
as a keyword argument. When a hook function is called, the local values override global values to
provide a single set of keyword arguments that are passed to the hook or callback.

In the example above would probably fire the hook with something like this::

    art.fire_hook('start_test', test_name="my_test", test_location="var/test/")

Notice that we don't specify what the artifact_path value is. In the concept of testing, we may
want to store multiple artifacts and so we would not want each plugin to have to compute the
artifact path for itself. Rather, we would create this path during a pre-hook callback and update
the local namespace with the key. So the process of events would follow like so.

1.  Local namespace has {test_name: "my_test", test_location: "var/test"}
2.  Prehook callback fires with the arguments [test_name, test_location]
3.  Prehook exits and updates the local namespace with artifact_path
4.  Local namespace has {test_name: "my_test", test_location: "var/test", artifact_path: "var/test/my_test"}
5.  Hook 'start_test' is called for the 'test' plugin with the arguments [test_name, test_location, artifact_path]
6.  Hook exits with no updates
7.  Posthook callback fires with the arguments [test_name, test_location, artifact_path]
8.  Posthook exits

See how the prehook sets up a key value which is the made available to all the other plugin hooks.

Configuration
-------------

Rigger takes few options to start, it, an example is shown below::

    squash_exceptions: True
    threaded: True
    plugins:
        test:
            enabled: True
            plugin: test

*  ``squash_exceptions`` option tells Rigger whether to ignore exceptions that happen inside
the ``fire_hook()`` call and just log them, or if it should raise them.
*  ``threaded`` option tells Rigger to run the fire_hook plugins as threads or sequentially.