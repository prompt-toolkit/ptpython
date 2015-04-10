from __future__ import unicode_literals

from pygments.token import Keyword, Operator, Number, Name, Error, Comment, Token, String
from pygments.style import Style


class PythonStyle(Style):
    background_color = None
    styles = {
        # Build-ins from the Pygments lexer.
        Comment:                                      '#0000dd',
        Error:                                        '#000000 bg:#ff8888',
        Keyword:                                      '#ee00ee',
        Name.Decorator:                               '#aa22ff',
        Name.Namespace:                               '#008800 underline',
        Name:                                         '#008800',
        Number:                                       '#ff0000',
        Operator:                                     '#ff6666 bold',
        String:                                       '#ba4444 bold',

        # Highlighting of search matches in document.
        Token.SearchMatch:                            '#ffffff bg:#4444aa',
        Token.SearchMatch.Current:                    '#ffffff bg:#44aa44',

        # Highlighting of select text in document.
        Token.SelectedText:                           '#ffffff bg:#6666aa',

        # (Python) Prompt: "In [1]:"
        Token.Layout.Prompt:                          'bold #008800',

        # Line numbers.
        Token.LineNumber:                             '#aa6666',

        Token.Separator:                              '#bbbbbb',

        # Search toolbar.
        Token.Toolbar.Search:                         '#22aaaa noinherit',
        Token.Toolbar.Search.Text:                    'noinherit',
        Token.Toolbar.Search.Text.NoMatch:            'bg:#aa4444 #ffffff',

        # System toolbar
        Token.Toolbar.System.Prefix:                  '#22aaaa noinherit',

        # "arg" toolbar.
        Token.Toolbar.Arg:                            '#22aaaa noinherit',
        Token.Toolbar.Arg.Text:                       'noinherit',

        # Signature toolbar.
        Token.Toolbar.Signature:                      'bg:#44bbbb #000000',
        Token.Toolbar.Signature.CurrentName:          'bg:#008888 #ffffff bold',
        Token.Toolbar.Signature.Operator:             '#000000 bold',

        Token.Docstring:                              '#888888',

        # Tab bar
        Token.TabBar:                                 '#888888 underline',
        Token.TabBar.Tab:                             'bg:#aaaaaa #444444',
        Token.TabBar.Tab.Active:                      'bg:#ffffff #000000 bold nounderline',

        # Validation toolbar.
        Token.Toolbar.Validation:                     'bg:#440000 #aaaaaa',

        # Status toolbar.
        Token.Toolbar.Status:                         'bg:#222222 #aaaaaa',
        Token.Toolbar.Status.InputMode:               'bg:#222222 #ffffaa',
        Token.Toolbar.Status.Off:                     'bg:#222222 #888888',
        Token.Toolbar.Status.On:                      'bg:#222222 #ffffff',
        Token.Toolbar.Status.PythonVersion:           'bg:#222222 #ffffff bold',

        # Completer toolbar.
        Token.Toolbar.Completions:                    'bg:#44bbbb #000000',
        Token.Toolbar.Completions.Arrow:              'bg:#44bbbb #000000 bold',
        Token.Toolbar.Completions.Completion:         'bg:#44bbbb #000000',
        Token.Toolbar.Completions.Completion.Current: 'bg:#008888 #ffffff',

        # Completer menu.
        Token.Menu.Completions.Completion:            'bg:#44bbbb #000000',
        Token.Menu.Completions.Completion.Current:    'bg:#008888 #ffffff',
        Token.Menu.Completions.Meta:                  'bg:#449999 #000000',
        Token.Menu.Completions.Meta.Current:          'bg:#00aaaa #000000',
        Token.Menu.Completions.ProgressBar:           'bg:#aaaaaa',
        Token.Menu.Completions.ProgressButton:        'bg:#000000',

        # When Control-C has been pressed. Grayed.
        Token.Aborted:                                '#888888',

        Token.Sidebar:                                'bg:#bbbbbb',
        Token.Sidebar.Shortcut:                       'bg:#bbbbbb #000011 bold',
        Token.Sidebar.Label:                          'bg:#bbbbbb #222222',
        Token.Sidebar.Status:                         'bg:#bbbbbb #000011 bold',

        # Matching bracket.
        Token.MatchingBracket:                        'bg:#aaaaff #000000',
    }
