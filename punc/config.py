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
#
# Copyright 2010 Andrew Fort

"""PUNC configuration parser."""


import logging
import yaml


class Error(Exception):
    pass


class RequiredAttributeMissingError(Error):
    """A required attribute was missing from the configuration file."""


class UnknownConfigurationFileFormatError(Error):
    """The configuration file extension was unknown."""


class Configuration(object):
    """PUNC's abstract configuration object."""

    def __init__(self, filename):
        self.filename = filename
        self.loaded = False
        self.config = {}
        try:
            self.config_file = open(self.filename)
        except (OSError, IOError), e:
            logging.error('Could not open config file. %s: %s',
                          e.__class__.__name__, str(e))
        else:
            self.load_config()
            self.after_load_config()
            if self.check_config():
                self.loaded = True

    def check_config(self):
        if not self.config.get('base_path'):
            raise RequiredAttributeMissingError(
                'Configuration file missing `base_path` top-level attribute.')
        else:
            return True

    def after_load_config(self):
        pass

    def load_config(self):
        raise NotImplementedError


class YamlConfiguration(Configuration):
    """A Yaml PUNC configuration (the default format)."""

    def __init__(self, filename):
        super(YamlConfiguration, self).__init__(filename)

    def load_config(self):
        try:
            self.config = yaml.load(self.config_file)
            # PyYAML may return a string if the file doesn't
            # parse as Yaml.  Empty files return None.
            if isinstance(self.config, str):
                self.config = {}
            if self.config is None:
                self.config = {}
            self.config_file.close()
        except yaml.error.YAMLError, e:
            logging.error('%s: %s', e.__class__.__name__, str(e))
            self.config = {}


def guess_config_file_format(filename):
    """Guesses the configuration file format based on extension."""
    if filename is None:
        return None
    for extension in CONFIG_FILE_EXTENSIONS.iterkeys():
        if filename.endswith(extension):
            return CONFIG_FILE_EXTENSIONS.get(extension)


def load_config_file(filename):
    """Loads a configuration file by name.

    Args:
      filename: A string, the config file name to load.

    Returns:
      An instance of a Configuration object subclass.

    Raises:
      errors.UnknownConfigurationFileFormatError:
        The file format was not recognised.
    """
    format_method = guess_config_file_format(filename)
    if format_method is not None:
        return format_method(filename)
    else:
        raise UnknownConfigurationFileFormatError(
            'Config file %s not supported; supported extensions: %s' %
            (filename, ', '.join(CONFIG_FILE_EXTENSIONS.keys())))


def get_config_from_file(filename):
    """Returns the configuration data from filename.

    Args:
      filename: A string, the config file name to load.

    Returns:
      A dict, the configuration object.

    Raises:
      errors.UnknownConfigurationFileFormatError:
        The file format was not recognised.
    """
    return load_config_file(filename).config


# Map of string configuration file extensions to class used
# to import such a configuration file.

# YAML files on most systems appear as 'ASCII text' to file(1), so we
# use this approach.
CONFIG_FILE_EXTENSIONS = {'.yaml': YamlConfiguration}
