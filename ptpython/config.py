"""
Ptpython settings loader from config file.
"""
import copy
import os
import re
import six
from six.moves.configparser import ConfigParser


option_re = re.compile('^(?P<option>\w+)\s+=.+(?P<comment>#.*)?$')


class Settings:
    """
    Ptpython user defined settings, loaded from <config-dir>/conf.cfg file.

    :param defaults: dictionary with repl's settings customisable in conf.cfg.
    """
    user_defined = {}

    def __init__(self, defaults=None):
        if defaults:
            for k, v in defaults.items():
                self.user_defined[k] = v
    
    def update_from(self, file_path):
        """
        Reads and loads user customised settings from the given file path.

        :param file_path: Absolute path to user settings file conf.cfg.
        """
        assert isinstance(file_path, six.text_type)

        cfg_parser = ConfigParser(inline_comment_prefixes=('#',))
        cfg_parser.read(file_path)
        ptpycfg = cfg_parser['ptpython']
        converters = [ConfigParser.getboolean,
                      ConfigParser.getint,
                      ConfigParser.getfloat]

        for key in ptpycfg:
            converted = False

            if key not in self.user_defined:
                # Only settings provided in initial defaults dict can get
                # customised with user defined values from conf.cfg file.
                continue

            for func in converters:
                try:
                    value = func(cfg_parser, 'ptpython', key)
                except ValueError:
                    continue
                else:
                    self.user_defined[key] = value
                    converted = True
                    break

            if not converted:
                self.user_defined[key] = ptpycfg.get(key, '')
    
    def __getattr__(self, name):
        if name in self.user_defined:
            return self.user_defined[name]
        else:
            raise AttributeError()

    def __setattr__(self, name, value):
        if name == 'user_defined':
            super(Settings, self).__setattr__(name, value)
        else:
            self.user_defined[name] = value

    def __dir__(self):
        dirlist = super(Settings, self).__dir__()
        dirlist.extend(self.user_defined.keys())
        dirlist.sort()
        return dirlist

    # ConfigParser write method doesn't preserve comments.
    # This is a rudimentary replacement to keep them that
    # works only for this very specific, one section based,
    # config file.
    def save_config(self, file_path='~/.ptpython/conf.cfg'):
        """
        Save settings in a given cfg file.

        :param file_path: Absolute path to user settings file conf.cfg.
        """
        assert isinstance(file_path, six.text_type)
        file_path = os.path.expanduser(file_path)

        # Read existing conf.cfg lines in current_lines,
        # so that they can be updated with new user defined values.
        current_lines = []

        settings = copy.copy(self.user_defined)

        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                current_lines = f.readlines()

        cfg_file = open(file_path, 'w')
        for line in current_lines:
            if line[0] in ['#', '[', '\n']:
                cfg_file.write(line)
            elif line[0].isalpha():
                match = option_re.search(line)
                if match:
                    key = match.group('option')
                    cmt = match.group('comment')
                    if cmt:
                        newline = '%s = %s # %s\n' % (key, str(settings.pop(key)), cmt)
                    else:
                        newline = '%s = %s\n' % (key, str(settings.pop(key)))
                    cfg_file.write(newline)

        if len(current_lines) == 0:
            # The conf.cfg file didn't exit before. The first line of the
            # file must be the section name between brackets.
            cfg_file.write('[ptpython]\n')

        # Write down the rest of the settings.
        for k, v in settings.items():
            newline = "%s = %s\n" % (k, str(v))
            cfg_file.write(newline)

        cfg_file.close()
