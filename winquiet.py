import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000


def install(popen=None, force=False):
    if not (force or sys.platform.startswith("win")):
        return False
    cls = popen or subprocess.Popen
    if getattr(cls, "_quiet", False):
        return False
    original = cls.__init__

    def quiet_init(self, *args, **kwargs):
        if len(args) < 14:
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NO_WINDOW
        original(self, *args, **kwargs)

    cls.__init__ = quiet_init
    cls._quiet = True
    return True
