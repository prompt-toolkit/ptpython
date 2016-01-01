"""
Ptpython settings loader from config file.
"""
import copy
import os
import re
import six
from six.moves.configparser import ConfigParser


option_re = re.compile('^(?P<option>\w+)\s+=.+(?P<comment>#.*)?$')

dynamic_settings = ['show_signature',
                    'show_docstring',
                    'show_meta_enter_message',
                    'completion_visualisation',
                    'completion_menu_scroll_offset',
                    'show_line_numbers',
                    'show_status_bar',
                    'wrap_lines',
                    'complete_while_typing',
                    'vi_mode', 'paste_mode',
                    'confirm_exit',
                    'accept_input_on_enter',
                    'enable_open_in_editor',
                    'enable_system_bindings',
                    'enable_input_validation',
                    'enable_auto_suggest',
                    'enable_mouse_support',
                    'enable_history_search',
                    'highlight_matching_parenthesis',
                    'show_sidebar',
                    'show_sidebar_help',
                    'terminal_title',
                    'exit_message',
                    'prompt_style']

class Settings:
    """
    Ptpython user defined settings, loaded from <config-dir>/conf.cfg file.

    :param defaults: dictionary with repl's settings customisable in conf.cfg.
    """
    def __init__(self, defaults=None):
        self.user_defined = {}
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
        if name in dynamic_settings and name in self.user_defined:
            return self.user_defined[name]
        else:
            raise AttributeError("setting '%s' is not supported" % name)

    def __setattr__(self, name, value):
        if name == 'user_defined':
            super(Settings, self).__setattr__(name, value)
        elif name in dynamic_settings:
            self.user_defined[name] = value
        else:
            raise AttributeError("setting '%s' is not supported" % name)

    def __dir__(self):
        dirlist = super(Settings, self).__dir__()
        dirlist.extend(self.user_defined.keys())
        dirlist.sort()
        return dirlist

    # ConfigParser's write method does not preserve comments.
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

        with open(file_path, 'w') as cfg_file:
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
