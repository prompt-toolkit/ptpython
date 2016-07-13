from prompt_toolkit.eventloop.base import EventLoop, INPUT_TIMEOUT
from prompt_toolkit.terminal.vt100_input import InputStream
from prompt_toolkit.eventloop.posix_utils import PosixStdinReader
from prompt_toolkit.eventloop.posix import call_on_sigwinch, DummyContext
from gevent import select

class GeventEventLoop(EventLoop):
    def __init__(self, *args, **kwargs):
        super(EventLoop, self).__init__()
        self.readers = dict()
        self._running = True
   
    def run(self, stdin, callbacks):
        inputstream = InputStream(callbacks.feed_key)
        stdin_reader = PosixStdinReader(stdin.fileno())
        #ctx = call_on_sigwinch(self.received_winch)
        ctx = DummyContext()
        
        with ctx:
            while self._running:
              r, _, _ = select.select([stdin.fileno()], [], [], INPUT_TIMEOUT)
              if r:
                  data = stdin_reader.read()
                  inputstream.feed(data)
                  if stdin_reader.closed:
                      break
              else:
                  # timeout
                  inputstream.flush()
                  callbacks.input_timeout()
                  continue

    def received_winch(self):
        pass

    def stop(self):
        """
        Stop the `run` call. (Normally called by
        :class:`~prompt_toolkit.interface.CommandLineInterface`, when a result
        is available, or Abort/Quit has been called.)
        """
        self._running = False

    def close(self):
        """
        Clean up of resources. Eventloop cannot be reused a second time after
        this call.
        """
        self.stop()
        self.readers = dict()

    def add_reader(self, fd, callback):
        """
        Start watching the file descriptor for read availability and then call
        the callback.
        """
        self.readers[fd] = gevent.get_hub().loop.io(fd, 1)
        self.readers[fd].start(callback)

    def remove_reader(self, fd):
        """
        Stop watching the file descriptor for read availability.
        """
        try:
            del self.readers[fd]
        except KeyError:
            pass

    def run_in_executor(self, callback):
        """
        Run a long running function in a background thread. (This is
        recommended for code that could block the event loop.)
        Similar to Twisted's ``deferToThread``.
        """
        gevent.spawn(callback)

    def call_from_executor(self, callback, _max_postpone_until=None):
        """
        Call this function in the main event loop. Similar to Twisted's
        ``callFromThread``.

        :param _max_postpone_until: `None` or `datetime` instance. For interal
            use. If the eventloop is saturated, consider this task to be low
            priority and postpone maximum until this timestamp. (For instance,
            repaint is done using low priority.)
        """
        gevent.spawn(callback)

