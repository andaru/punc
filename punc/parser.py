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

"""PUNC's library of text parsing routines."""

import re


BLANK_LINE = re.compile(r'^\s*$')


class Error(Exception):
    """A parser error occured."""


class DeviceReportedError(Error):
    """The device reports an error in its response."""


class SkipResult(Error):
    """The parser indicates that the result should be ignored."""


class Parser(object):
    """A PUNC parser."""

    def __init__(self, input_data):
        """Parser object.

        Args:
          input_data: The input as a 'text string' (w/embedded newlines).
        """
        self._input_data = input_data
        self.input = input_data.split('\n')

    def parse(self):
        """Clients should call this method."""
        return self._parse()

    def _parse(self):
        """Subclasses should override this method to parse."""
        # Return what we were provided.
        return '\n'.join(self.input)


class NullParser(Parser):
    """A do-nothing parser for binary results."""

    def __init__(self, input_data):
        self._input_data = input_data

    def _parse(self):
        return self._input_data


class AddDropParser(Parser):
    """A text parser that has keep ot drop lines based on regexps."""

    INC_RE = tuple()
    DROP_RE = tuple()
    IGNORE_RE = tuple()
    ERROR_RE = tuple()

    flag_drop = True
    flag_inc = True
    flag_ignore = True
    flag_error = True
    flag_trailing_blank = True
    commented = False
    comment = ''

    def _parse(self):
        """Parses the text block."""
        result = []
        if self.commented:
            comment = self.comment
        else:
            comment = ''

        for line in self.input:
            dropped = False
            if self.flag_ignore:
                for re in self.IGNORE_RE:
                    m = re.search(line)
                    if m:
                        raise SkipResult(m.group(0))
            if self.flag_error:
                for re in self.ERROR_RE:
                    m = re.search(line)
                    if m:
                        raise DeviceReportedError('Error from device: %s' %
                                                  m.group(0))
            if self.flag_drop:
                for re in self.DROP_RE:
                    if re.search(line):
                        # Matched a drop line, so just skip it.
                        dropped = True
                        break

            if len(self.INC_RE) and self.flag_inc:
                for re in self.INC_RE:
                    match = re.search(comment + line)
                    if match:
                        result.append(comment + line)
            elif not dropped:
                if line:
                    result.append(comment + line)

        result = '\n'.join(result)
        if self.flag_trailing_blank:
            if self.comment:
                return result + '\n%s\n' % self.comment
            else:
                return result + '\n'
        else:
            return result
