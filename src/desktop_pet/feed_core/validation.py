from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .model import ConfirmationTarget, FileIdentity


class Rejection(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedFile:
    path: Path
    name: str
    identity: FileIdentity
    confirmation: ConfirmationTarget

    @property
    def fingerprint(self) -> str:
        return self.identity.fingerprint


class FileValidator:
    def __init__(self, *, protected_roots=None, application_path=None, repository_root=None):
        self.application_path = Path(application_path or os.path.abspath(os.sys.argv[0])).resolve()
        self.repository_root = Path(repository_root or Path.cwd()).resolve()
        if protected_roots is None:
            protected_roots = [
                value
                for key in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData")
                if (value := os.environ.get(key))
            ]
        self.protected_roots = tuple(Path(item).resolve() for item in protected_roots)

    @staticmethod
    def _within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _identity(path: Path, info: os.stat_result) -> FileIdentity:
        fields = (
            path.name,
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )
        encoded = "\0".join(str(value) for value in fields).encode("utf-8", "surrogatepass")
        return FileIdentity(
            device=info.st_dev,
            inode=info.st_ino,
            mode=info.st_mode,
            size_bytes=info.st_size,
            modified_ns=info.st_mtime_ns,
            changed_ns=info.st_ctime_ns,
            fingerprint=hashlib.sha256(encoded).hexdigest(),
        )

    def validate(self, candidate, *, explicitly_dropped: bool) -> ValidatedFile:
        if not explicitly_dropped:
            raise Rejection("不是本次明确拖入的对象")
        raw = Path(candidate)
        if os.name == "nt" and str(raw).startswith(("\\\\", "//")):
            raise Rejection("拒绝网络路径")
        try:
            info = raw.lstat()
        except OSError as error:
            raise Rejection("对象不可访问") from error
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise Rejection("拒绝链接或重解析点")
        path = raw.resolve()
        if path == Path(path.anchor) or not stat.S_ISREG(info.st_mode) or not path.is_file():
            raise Rejection("只接受普通文件")
        if path == self.application_path:
            raise Rejection("拒绝程序自身")
        if self._within(path, self.repository_root) or any(
            self._within(path, root) for root in self.protected_roots
        ):
            raise Rejection("拒绝仓库、素材、系统或受保护对象")
        if not os.access(path, os.R_OK | os.W_OK):
            raise Rejection("对象受保护")
        identity = self._identity(path, info)
        return ValidatedFile(
            path=path,
            name=path.name,
            identity=identity,
            confirmation=ConfirmationTarget(path.name, info.st_size, info.st_mtime_ns),
        )
