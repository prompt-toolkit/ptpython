"""
Ptpython settings loader from config file.
"""
import re
from configparser import ConfigParser


option_re = re.compile('^(?P<option>\w+)\s+=.+(?P<comment>#.*)?$')


class Settings:
    user_defined = {}
    file_path = None

    def __init__(self, defaults=None):
        if defaults:
            for k, v in defaults.items():
                self.user_defined[k] = v
    
    def update_from(self, file_path):
        self.file_path = file_path
        cfg_parser = ConfigParser(inline_comment_prefixes=('#',))
        cfg_parser.read(self.file_path)
        ptpycfg = cfg_parser['ptpython']
        converters = [ConfigParser.getboolean,
                      ConfigParser.getint,
                      ConfigParser.getfloat]
        for key in ptpycfg:
            converted = False
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
        if name in ['user_defined', 'file_path']:
            super(Settings, self).__setattr__(name, value)
        else:
            self.user_defined[name] = value

    def __dir__(self):
        dirlist = super(Settings, self).__dir__()
        dirlist.extend(self.user_defined.keys())
        dirlist.sort()
        return dirlist

    def save_config(self):
        # ConfigParser write method doesn't preserve comments.
        # This is a rudimentary replacement to keep them that
        # works only for this very specific, one section based,
        # config file.
        with open(self.file_path, 'r') as f:
            lines = f.readlines()
        cfg_file = open(self.file_path, 'w')
        for line in lines:
            if line[0] in ['#', '[', '\n']:
                cfg_file.write(line)
            elif line[0].isalpha():
                match = option_re.search(line)
                if match:
                    key = match.group('option')
                    cmt = match.group('comment')
                    if cmt:
                        newline = '%s = %s # %s\n' % (
                            key, str(self.user_defined[key]), cmt)
                    else:
                        newline = '%s = %s\n' % (
                            key, str(self.user_defined[key]))
                    cfg_file.write(newline)
        cfg_file.close()
