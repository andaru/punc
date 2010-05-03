import re


BLANK_LINE = re.compile('^\s*$')


class Error(Exception):
    """A parser error occured."""


class DeviceReportedError(Error):
    """The device reports an error in its response."""

    
class IgnoreResultError(Error):
    """The parser indicates that the result should be ignored."""


class Parser(object):
              
    def __init__(self, input_text):
        """Text parser object.

        Args:
          input_text: The input text as a string (w/embedded newlines).
        """
        self.input = input_text.split('\n')

    def Parse(self):
        """Clients should call this method."""
        return self._Parse()

    def _Parse(self):
        """Subclasses should override this method to parse."""
        # Return what we were provided.
        return '\n'.join(self.input)


class AddDropParser(Parser):

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

    def _Parse(self):
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
                        raise IgnoreResultError('Ignored due to: %s' %
                                                m.group(0))
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
