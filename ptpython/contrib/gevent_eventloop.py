from prompt_toolkit.eventloop.base import EventLoop, INPUT_TIMEOUT
from prompt_toolkit.terminal.vt100_input import InputStream
from prompt_toolkit.eventloop.posix_utils import PosixStdinReader
from prompt_toolkit.eventloop.posix import call_on_sigwinch, DummyContext, in_main_thread
from prompt_toolkit.eventloop.select import fd_to_int
from gevent import select
import time
import os

class GeventEventLoop(EventLoop):
    def __init__(self, *args, **kwargs):
        super(EventLoop, self).__init__()
        self.readers = dict()
        self._running = True
        self._schedule_pipe_read,self._schedule_pipe_write = os.pipe()
        self._calls_from_executor = list()
        self._callbacks = None
        self._winch_callback_done = True

    def run(self, stdin, callbacks):
        inputstream = InputStream(callbacks.feed_key)
        stdin_reader = PosixStdinReader(stdin.fileno())
        self._callbacks = callbacks

        if in_main_thread():
            ctx = call_on_sigwinch(self.received_winch)
        else:
            ctx = DummyContext()
        
        select_timeout = INPUT_TIMEOUT
        with ctx:
            while self._running:
              r, _, _ = select.select([stdin.fileno(),self._schedule_pipe_read],
                                      [], [],select_timeout)
              if stdin.fileno() in r:
                  select_timeout = INPUT_TIMEOUT
                  data = stdin_reader.read()
                  inputstream.feed(data)
                  if stdin_reader.closed:
                      break
              elif self._schedule_pipe_read in r:
                  os.read(self._schedule_pipe_read,8192)
                  while True:
                      try:
                          task = self._calls_from_executor.pop(0)
                      except IndexError:
                          break
                      else:
                          task()
              else:
                  # timeout
                  inputstream.flush()
                  callbacks.input_timeout()
                  select_timeout = None

        self._callbacks = None

    def received_winch(self):
        def process_winch():
            if self._callbacks:
                self._callbacks.terminal_size_changed()
            self._winch_callback_done = True

        if self._winch_callback_done:
            self._winch_callback_done = False
            self.call_from_executor(process_winch)

    def stop(self):
        """
        Stop the `run` call. (Normally called by
        :class:`~prompt_toolkit.interface.CommandLineInterface`, when a result
        is available, or Abort/Quit has been called.)
        """
        self._running = False
        try:
            os.write(self._schedule_pipe_write,'x')
        except (AttributeError, IndexError, OSError):
            pass

    def close(self):
        """
        Clean up of resources. Eventloop cannot be reused a second time after
        this call.
        """
        self.stop()
        for reader in self.readers.values():
            reader.kill()
        self.readers = dict()
        self._callbacks = None

    def add_reader(self, fd, callback):
        """
        Start watching the file descriptor for read availability and then call
        the callback.
        """
        fd = fd_to_int(fd)
        self.readers[fd] = gevent.get_hub().loop.io(fd, 1)
        self.readers[fd].start(callback)

    def remove_reader(self, fd):
        """
        Stop watching the file descriptor for read availability.
        """
        fd = fd_to_int(fd)
        task = self.readers.pop(fd,None)
        if task is not None:
            task.kill()
        
    def run_in_executor(self, callback):
        """
        Run a long running function in a background thread. (This is
        recommended for code that could block the event loop.)
        Similar to Twisted's ``deferToThread``.
        """
        self.call_from_executor(callback)

    def call_from_executor(self, callback, _max_postpone_until=None):
        """
        Call this function in the main event loop. Similar to Twisted's
        ``callFromThread``.

        :param _max_postpone_until: `None` or `datetime` instance. For interal
            use. If the eventloop is saturated, consider this task to be low
            priority and postpone maximum until this timestamp. (For instance,
            repaint is done using low priority.)
        """
        if _max_postpone_until is None:
            def start_executor():
                gevent.spawn(callback)
            self._calls_from_executor.append(start_executor)
        else:
            def postpone():
                sleep_time = _max_postpone_until - time.time()
                if sleep_time > 0:
                    gevent.sleep(sleep_time)
                callback()
            self._calls_from_executor.append(postpone)
        try:
            os.write(self._schedule_pipe_write,'x')
        except (AttributeError, IndexError, OSError):
            pass
