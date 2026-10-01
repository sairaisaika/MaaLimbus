"""One OS lock shared by native CLI and packaged Agent entry points."""
from pathlib import Path

_leases={}


class ControllerLease:
    def __init__(self,path):
        import msvcrt
        self.path=Path(path).resolve()
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
        key=str(Path(path).resolve())
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
