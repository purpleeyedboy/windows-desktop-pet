from __future__ import annotations
import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

class Rejection(ValueError): pass

@dataclass(frozen=True)
class ValidatedFile:
    path: Path
    name: str
    fingerprint: str

class FileValidator:
    def __init__(self, *, protected_roots=None, application_path=None, repository_root=None):
        self.application_path=Path(application_path or os.path.abspath(os.sys.argv[0])).resolve()
        self.repository_root=Path(repository_root or Path.cwd()).resolve()
        if protected_roots is None:
            protected_roots=[p for key in ('WINDIR','ProgramFiles','ProgramFiles(x86)','ProgramData') if (p:=os.environ.get(key))]
        self.protected_roots=tuple(Path(p).resolve() for p in protected_roots)

    @staticmethod
    def _within(path: Path, root: Path) -> bool:
        try: path.relative_to(root); return True
        except ValueError: return False

    def validate(self, candidate, *, explicitly_dropped: bool) -> ValidatedFile:
        if not explicitly_dropped: raise Rejection('不是本次明确拖入的对象')
        raw=Path(candidate)
        if os.name=='nt' and str(raw).startswith(('\\\\','//')): raise Rejection('拒绝网络路径')
        try: info=raw.lstat()
        except OSError as error: raise Rejection('对象不可访问') from error
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0) & 0x400:
            raise Rejection('拒绝链接或重解析点')
        path=raw.resolve()
        if path == Path(path.anchor) or not path.is_file(): raise Rejection('只接受普通文件')
        if path == self.application_path: raise Rejection('拒绝程序自身')
        if self._within(path,self.repository_root) or any(self._within(path,r) for r in self.protected_roots):
            raise Rejection('拒绝仓库、素材、系统或受保护对象')
        if not os.access(path,os.R_OK|os.W_OK): raise Rejection('对象受保护')
        identity=f'{path.name}\0{info.st_dev}\0{info.st_ino}\0{info.st_size}\0{info.st_mtime_ns}'.encode('utf-8','surrogatepass')
        return ValidatedFile(path,path.name,hashlib.sha256(identity).hexdigest())
