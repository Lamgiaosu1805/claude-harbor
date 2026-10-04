"""Install bundled runtime atomically; never bundle or overwrite login/session data."""
import fcntl, os, shutil, sys, tempfile
from pathlib import Path
import profile_store as store
FILES=('profile_store.py','manager.py','desktop_launcher.py','desktop_sync.py','history_inventory.py','clone-entitlements.plist')

def install_runtime(source):
    store.ROOT.mkdir(parents=True,exist_ok=True)
    with (store.ROOT/'sync.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        backup=store.ROOT/'runtime-backups';backup.mkdir(exist_ok=True)
        for name in FILES:
            original=source/name; target=store.ROOT/name
            if target.exists() and target.read_bytes()==original.read_bytes():continue
            if target.exists():shutil.copy2(target,backup/(name+'.previous'))
            fd,temporary=tempfile.mkstemp(prefix='.runtime-',dir=store.ROOT)
            try:
                with os.fdopen(fd,'wb') as f:f.write(original.read_bytes());f.flush();os.fsync(f.fileno())
                os.replace(temporary,target)
            finally:
                if Path(temporary).exists():Path(temporary).unlink()
        if not store.REGISTRY.exists():store.save([])
    return store.ROOT

if __name__=='__main__':print(install_runtime(Path(__file__).parent))
