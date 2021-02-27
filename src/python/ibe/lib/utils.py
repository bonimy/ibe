import errno
import subprocess
import threading


def xs_bool(val, default=False):
    """Maps a string conforming to the xs:boolean XML Schema type
    to a Python bool.
    """
    if val is None:
        return default
    if val in ("true", "1"):
        return True
    return False

def call(args):
    """Launches a sub-process with the specified arguments, and returns
    its output as a string.
    """
    p = subprocess.Popen(args, stdout=subprocess.PIPE, close_fds=True)
    try:
        msg = p.stdout.read()
        return msg
    finally:
        stop = False
        while not stop:
            try:
                p.wait()
                stop = True
            except OSError, e:
                # IF SIGCHLD has been set to SIG_IGN or the SA_NOCLDWAIT flag
                # has been applied to SIGCHLD, then the child process may no
                # longer be around to wait on
                if e.errno == errno.ECHILD:
                    stop = True
                elif e.errno != errno.EINTR:
                    raise e


class NoopContextMgr(object):
    """A no-op context manager.
    """
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): pass
    def __exit__(self, exc_type, exc_val, exc_tb): return False

class Swallow(object):
    """A context manager that swallows exceptions.
    """
    def __enter__(self): pass
    def __exit__(self, exc_type, exc_val, exc_tb): return True

class _Generator:
    def __init__(self, generator, callback, environ):
        self._generator = generator
        self._callback = callback
        self._environ = environ
    def __iter__(self):
        for item in self._generator:
            yield item
    def close(self):
        if hasattr(self._generator, 'close'):
            self._generator.close()
        self._callback(self._environ)

class ExecuteOnCompletion:
    """Execute a callback after completion of a WSGI application.
    """
    def __init__(self, application, callback):
        self._application = application
        self._callback = callback
    def __call__(self, environ, start_response):
        try:
            result = self._application(environ, start_response)
        except:
            self._callback(environ)
            raise
        return _Generator(result, self._callback, environ)
