"""One OS lock shared by native CLI and packaged Agent entry points."""
from pathlib import Path
import os

_leases={}


def lease_path(path):
    path = Path(path)
    # A source CLI and an installed Agent have different roots. The controller
    # lock must survive app replacement and exclude both of them system-wide.
    if path.name == 'controller.lock':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))
        return (base/'MaaLimbus/controller.lock').resolve()
    return path.resolve()


class LeaseUnavailable(RuntimeError):
    """The lease file exists but could not be opened or locked."""


class ControllerLease:
    def __init__(self,path):
        import msvcrt
        self.path=lease_path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        # A lease file that is briefly unreadable (deleted by a cleanup script while a
        # handle was still open, or held for a moment) used to surface as a raw
        # `PermissionError` traceback from the harness.  Retry once, then say what it
        # is: the caller can report a refusal instead of a Python crash.
        last=None
        for attempt in range(2):
            try:
                self.file=self.path.open('a+b')
                self.file.seek(0)
                if not self.file.read(1):
                    self.file.write(b'0');self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
                break
            except PermissionError as error:
                last=error
                try:
                    self.file.close()
                except (AttributeError,OSError):
                    pass
                if attempt:
                    raise LeaseUnavailable('the_lease_file_is_not_readable') from error
                import time as _time
                _time.sleep(.2)
            except BaseException:
                try: self.file.close()
                except (AttributeError,OSError): pass
                raise

    @classmethod
    def acquire(cls,path):
        key=str(lease_path(path))
        lease=_leases.get(key)
        if lease is None or lease.file.closed:
            lease=cls(path);_leases[key]=lease
        return lease

    def close(self):
        if not self.file.closed:
            import msvcrt
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1)
            self.file.close()
