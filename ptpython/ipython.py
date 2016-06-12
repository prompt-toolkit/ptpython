"""

Adaptor for using the input system of `prompt_toolkit` with the IPython
backend.

This gives a powerful interactive shell that has a nice user interface, but
also the power of for instance all the %-magic functions that IPython has to
offer.

"""
from __future__ import unicode_literals, print_function

from prompt_toolkit.completion import Completion, Completer
from prompt_toolkit.contrib.completers import PathCompleter, WordCompleter, SystemCompleter
from prompt_toolkit.contrib.regular_languages.compiler import compile
from prompt_toolkit.contrib.regular_languages.completion import GrammarCompleter
from prompt_toolkit.contrib.regular_languages.lexer import GrammarLexer
from prompt_toolkit.document import Document
from prompt_toolkit.interface import CommandLineInterface
from prompt_toolkit.layout.lexers import PygmentsLexer, SimpleLexer

from .python_input import PythonInput, PythonValidator, PythonCompleter
from .eventloop import create_eventloop
from .style import default_ui_style

from IPython.terminal.embed import InteractiveShellEmbed as _InteractiveShellEmbed
from IPython.terminal.ipapp import load_default_config
from IPython import utils as ipy_utils
from IPython.core.inputsplitter import IPythonInputSplitter

from pygments.lexers import PythonLexer, BashLexer
from pygments.token import Token
from ptpython.prompt_style import PromptStyle

__all__ = (
    'embed',
)


class IPythonPrompt(PromptStyle):
    """
    PromptStyle that uses the templates, as set by IPython.
    Usually, something like "In [1]:".
    """
    def __init__(self, prompt_manager):
        self.prompt_manager = prompt_manager

    def in_tokens(self, cli):
        text = self.prompt_manager.render('in', color=False, just=False)
        return [(Token.In, text)]

    def in2_tokens(self, cli, width):
        text = self.prompt_manager.render('in2', color=False, just=False)
        return [(Token.In, text.rjust(width))]

    def out_tokens(self, cli):
        # This function is currently not used by IPython. But for completeness,
        # it would look like this.
        text = self.prompt_manager.render('out', color=False, just=False)
        return [(Token.Out, text)]


class IPython5Prompt(PromptStyle):
    """
    Style for IPython >5.0, use the prompt_toolkit tokens directly.
    """
    def __init__(self, prompts):
        self.prompts = prompts

    def in_tokens(self, cli):
        return self.prompts.in_prompt_tokens(cli)

    def in2_tokens(self, cli, width):
        return self.prompts.continuation_prompt_tokens(cli)

    def out_tokens(self, cli):
        return []


class IPythonValidator(PythonValidator):
    def __init__(self, *args, **kwargs):
        super(IPythonValidator, self).__init__(*args, **kwargs)
        self.isp = IPythonInputSplitter()

    def validate(self, document):
        document = Document(text=self.isp.transform_cell(document.text))
        super(IPythonValidator, self).validate(document)


def create_ipython_grammar():
    """
    Return compiled IPython grammar.
    """
    return compile(r"""
        \s*
        (
            (?P<percent>%)(
                (?P<magic>pycat|run|loadpy|load)  \s+ (?P<py_filename>[^\s]+)  |
                (?P<magic>cat)                    \s+ (?P<filename>[^\s]+)     |
                (?P<magic>pushd|cd|ls)            \s+ (?P<directory>[^\s]+)    |
                (?P<magic>pdb)                    \s+ (?P<pdb_arg>[^\s]+)      |
                (?P<magic>autocall)               \s+ (?P<autocall_arg>[^\s]+) |
                (?P<magic>time|timeit|prun)       \s+ (?P<python>.+)           |
                (?P<magic>psource|pfile|pinfo|pinfo2) \s+ (?P<python>.+)       |
                (?P<magic>system)                 \s+ (?P<system>.+)           |
                (?P<magic>unalias)                \s+ (?P<alias_name>.+)       |
                (?P<magic>[^\s]+)   .* |
            ) .*            |
            !(?P<system>.+) |
            (?![%!]) (?P<python>.+)
        )
        \s*
    """)


def create_completer(get_globals, get_locals, magics_manager, alias_manager):
    g = create_ipython_grammar()

    return GrammarCompleter(g, {
        'python': PythonCompleter(get_globals, get_locals),
        'magic': MagicsCompleter(magics_manager),
        'alias_name': AliasCompleter(alias_manager),
        'pdb_arg': WordCompleter(['on', 'off'], ignore_case=True),
        'autocall_arg': WordCompleter(['0', '1', '2'], ignore_case=True),
        'py_filename': PathCompleter(only_directories=False, file_filter=lambda name: name.endswith('.py')),
        'filename': PathCompleter(only_directories=False),
        'directory': PathCompleter(only_directories=True),
        'system': SystemCompleter(),
    })


def create_lexer():
    g = create_ipython_grammar()

    return GrammarLexer(
        g,
        lexers={
            'percent': SimpleLexer(Token.Operator),
            'magic': SimpleLexer(Token.Keyword),
            'filename': SimpleLexer(Token.Name),
            'python': PygmentsLexer(PythonLexer),
            'system': PygmentsLexer(BashLexer),
        })


class MagicsCompleter(Completer):
    def __init__(self, magics_manager):
        self.magics_manager = magics_manager

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()

        for m in sorted(self.magics_manager.magics['line']):
            if m.startswith(text):
                yield Completion('%s' % m, -len(text))


class AliasCompleter(Completer):
    def __init__(self, alias_manager):
        self.alias_manager = alias_manager

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        #aliases = [a for a, _ in self.alias_manager.aliases]
        aliases = self.alias_manager.aliases

        for a, cmd in sorted(aliases, key=lambda a: a[0]):
            if a.startswith(text):
                yield Completion('%s' % a, -len(text),
                                 display_meta=cmd)


class IPythonInput(PythonInput):
    """
    Override our `PythonCommandLineInterface` to add IPython specific stuff.
    """
    def __init__(self, ipython_shell, *a, **kw):
        kw['_completer'] = create_completer(kw['get_globals'], kw['get_globals'],
                                            ipython_shell.magics_manager,
                                            ipython_shell.alias_manager)
        kw['_lexer'] = create_lexer()
        kw['_validator'] = IPythonValidator(
            get_compiler_flags=self.get_compiler_flags)

        super(IPythonInput, self).__init__(*a, **kw)
        self.ipython_shell = ipython_shell

        # Prompt for IPython < 5.0
        if hasattr(ipython_shell, 'prompt_manager'):
            self.all_prompt_styles['ipython'] = IPythonPrompt(ipython_shell.prompt_manager)
            self.prompt_style = 'ipython'

        # Prompt for IPython >=5.0:
        if hasattr(ipython_shell, 'prompts'):
            self.all_prompt_styles['ipython'] = IPython5Prompt(ipython_shell.prompts)
            self.prompt_style = 'ipython'


        # UI style for IPython. Add tokens that are used by IPython>5.0
        style_dict = {}
        style_dict.update(default_ui_style)
        style_dict.update({
            Token.Prompt:        '#009900',
            Token.PromptNum:     '#00ff00 bold',
            Token.OutPrompt:     '#990000',
            Token.OutPromptNum:  '#ff0000 bold',
        })

        self.ui_styles = {
            'default': style_dict,
        }
        self.use_ui_colorscheme('default')


class InteractiveShellEmbed(_InteractiveShellEmbed):
    """
    Override the `InteractiveShellEmbed` from IPython, to replace the front-end
    with our input shell.

    :param configure: Callable for configuring the repl.
    """
    def __init__(self, *a, **kw):
        vi_mode = kw.pop('vi_mode', False)
        history_filename = kw.pop('history_filename', None)
        configure = kw.pop('configure', None)
        title = kw.pop('title', None)

        super(InteractiveShellEmbed, self).__init__(*a, **kw)

        def get_globals():
            return self.user_ns

        self._eventloop = create_eventloop()
        ipython_input = IPythonInput(
            self,
            get_globals=get_globals, vi_mode=vi_mode,
            history_filename=history_filename)

        if title:
            ipython_input.terminal_title = title

        if configure:
            configure(ipython_input)
            ipython_input.prompt_style = 'ipython'  # Don't take from config.

        self._cli = CommandLineInterface(
                application=ipython_input.create_application(),
                eventloop=self._eventloop)

    def prompt_for_code(self):
        # IPython 5.0 calls `prompt_for_code` instead of `raw_input`.
        return self.raw_input(self)

    def raw_input(self, prompt=''):
        print('')
        try:
            string = self._cli.run(reset_current_buffer=True).text

            # In case of multiline input, make sure to append a newline to the input,
            # otherwise, IPython will ask again for more input in some cases.
            if '\n' in string:
                return string + '\n\n'
            else:
                return string
        except EOFError:
            self.ask_exit()
            return ''


def initialize_extensions(shell, extensions):
    """
    Partial copy of `InteractiveShellApp.init_extensions` from IPython.
    """
    try:
        iter(extensions)
    except TypeError:
        pass  # no extensions found
    else:
        for ext in extensions:
            try:
                shell.extension_manager.load_extension(ext)
            except:
                ipy_utils.warn.warn(
                    "Error in loading extension: %s" % ext +
                    "\nCheck your config files in %s" % ipy_utils.path.get_ipython_dir())
                shell.showtraceback()


def embed(**kwargs):
    """
    Copied from `IPython/terminal/embed.py`, but using our `InteractiveShellEmbed` instead.
    """
    config = kwargs.get('config')
    header = kwargs.pop('header', u'')
    compile_flags = kwargs.pop('compile_flags', None)
    if config is None:
        config = load_default_config()
        config.InteractiveShellEmbed = config.TerminalInteractiveShell
        kwargs['config'] = config
    shell = InteractiveShellEmbed.instance(**kwargs)
    initialize_extensions(shell, config['InteractiveShellApp']['extensions'])
    shell(header=header, stack_depth=2, compile_flags=compile_flags)
