#!/bin/env python

# Copyright 2010 Andrew Fort


import unittest

import punc.collection


class MockNotchConnection(object):

    def __init__(self):
        self.exec_req_called = False
        self.devices_info_called = False
        self.device_names = set()

    def devices_info(self, reg):
        self.devices_info_called = True
        return {'r1': {}, 'r2': {}}

    def exec_requests(self, notch_requests):
        self.exec_req_called = True
        result = set()
        for r in notch_requests:
            result.add(r.arguments.get('device_name'))
        for r in result:
            self.device_names.add(r)

            
class CollectionTest(unittest.TestCase):

    def setUp(self):
        self._collection1 = punc.collection.Collection(
            'test1',
            {'recipes': [{'vendor': 'cisco',
                        'ruleset': 'cisco',
                        'regexp': r'.*',
                        'path': 'cisco'},
                       {'vendor': 'juniper',
                        'ruleset': 'juniper',
                        'regexp': r'.*',
                        'path': 'juniper'}],
             'order': 1},
            path='./basepath')

    def testParseConfig(self):
        self.assertEqual(len(self._collection1.recipes), 2)

    def testCollect(self):
        nc = MockNotchConnection()
        self.assertEqual(nc.exec_req_called, False)
        self.assertEqual(nc.devices_info_called, False)
        self._collection1.collect(nc)
        self.assertEqual(nc.exec_req_called, True)
        self.assertEqual(nc.devices_info_called, True)
        self.assert_('r1' in nc.device_names)
        self.assert_('r2' in nc.device_names)


if __name__ == '__main__':
    unittest.main()
