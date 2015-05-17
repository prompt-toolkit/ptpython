import ConfigParser

def getSettings():
    def ConfigSectionMap(Config, section):
        dict1 = {}
        options = Config.options(section)
        for option in options:
            try:
                dict1[option] = Config.get(section, option)
                if dict1[option] == -1:
                    DebugPrint("skip: %s" % option)
            except:
                print("exception on %s!" % option)
                dict1[option] = None
        return dict1

    from os.path import expanduser
    default_on_start = {'sidebar'       : 'F2',
               'completion menu'        : 'pop-up',
               'input mode'             : 'emacs',
               'complete while typying' : 'True',
               'paste mode'             : 'False',
               'show signature'         : 'True',
               'show docstring'         : 'False',
               'show linenumbers'       : 'True'}

    default_keymaps = { 'sidebar'               : 'F2',
                        'completion menu'       : 'F3',
                        'input mode'            : 'F4',
                        'complete while typing' : 'F5',
                        'paste mode'            : 'F6',
                        'show signature'        : 'F8',
                        'show docstring'        : 'F9',
                        'show line numbers'     : 'F10'}

    config_file = expanduser("~/.ptpython")

    config = ConfigParser.ConfigParser()
    config.read(config_file)

    if 'Keymaps' in config.sections():
        keymaps = ConfigSectionMap(config, 'Keymaps')
        for key, value in keymaps.iteritems():
            default_keymaps[key] = value

    if 'Startup' in config.sections():
        on_start = ConfigSectionMap(config, 'Startup')
        for key, value in on_start.iteritems():
            default_on_start[key] = value
    return default_on_start, default_keymaps
