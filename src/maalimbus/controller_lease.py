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


class ControllerLease:
    def __init__(self,path):
        import msvcrt
        self.path=lease_path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.path.open('a+b')
        try:
            self.file.seek(0)
            if not self.file.read(1):
                self.file.write(b'0');self.file.flush()
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
        except BaseException:
            self.file.close();raise

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
