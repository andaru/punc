#!/usr/bin/env python
#
# Copyright 2010 Andrew Fort
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import setuptools


setuptools.setup(
    name='punc',
    version='0.2.3',
    description='Pick Up Network (Device) Configuration',

    entry_points = {
        'console_scripts': [
            'punc = punc.main:main'
            ]
        },

    install_requires=['mercurial',
                      'notch.client',
                      'PyYAML',
                      ],

    url='http://code.google.com/p/punc/',
    author='Andrew Fort',
    author_email='notch-dev@googlegroups.com',
    license='http://www.apache.org/licenses/LICENSE-2.0',

    classifiers=['Development Status :: 2 - Pre-Alpha',
                 'Environment :: Console',
                 'Intended Audience :: System Administrators',
                 'License :: OSI Approved :: Apache Software License',
                 'Operating System :: POSIX',
                 'Programming Language :: Python :: 2.6',
                 'Topic :: System :: Networking :: Monitoring',
                 'Topic :: System :: Systems Administration',
                 ],

    packages = setuptools.find_packages(),
    test_suite='tests',
    zip_safe = True,
    )
