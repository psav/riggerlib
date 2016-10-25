""" Test plugin for Artifactor """

from .. import RiggerBasePlugin


class Test(RiggerBasePlugin):

    def plugin_initialize(self):
        self.register_plugin_hook('start_test', self.start_test)
        self.register_plugin_hook('finish_test', self.finish_test)

    def start_test(self, test_name, test_location):
        return None, {'test': {"start": True}}

    def finish_test(self, test_name, test_location):
        return None, {'test': {"finish": True}}
