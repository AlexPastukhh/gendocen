"""Stable resource and field references used by the documentation engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from urllib.parse import quote, unquote, urlsplit


_NAMESPACE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_LOCAL_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


class RefError(ValueError):
    """Raised when a resource reference is malformed, unsafe or non-canonical."""


def _decode_pointer_token(token: str) -> str:
    # RFC 6901 requires only ~0 and ~1 escapes. Reject dangling/unknown escapes.
    out: list[str] = []
    i = 0
    while i < len(token):
        if token[i] != "~":
            out.append(token[i])
            i += 1
            continue
        if i + 1 >= len(token) or token[i + 1] not in "01":
            raise RefError(f"invalid JSON Pointer escape in token: {token!r}")
        out.append("~" if token[i + 1] == "0" else "/")
        i += 2
    return "".join(out)


def _encode_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def parse_json_pointer(pointer: str | None) -> tuple[str, ...]:
    if pointer in (None, ""):
        return ()
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise RefError("JSON Pointer must be empty or start with '/'")
    return tuple(_decode_pointer_token(part) for part in pointer[1:].split("/"))


def format_json_pointer(parts: tuple[str, ...]) -> str:
    if not parts:
        return ""
    return "/" + "/".join(_encode_pointer_token(part) for part in parts)


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """Address a managed resource or a whole plain documentation file.

    Canonical v0.1 forms:
      resource://<namespace>/<id>#/<json-pointer>
      file://<documentation-relative-path>

    Direct dataclass construction is validated too; callers cannot bypass canonical
    identity rules merely by constructing a ``ResourceRef`` instead of parsing text.
    """

    scheme: str
    namespace: str | None = None
    resource_id: str | None = None
    file_path: str | None = None
    pointer_parts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.scheme == "resource":
            if self.file_path is not None:
                raise RefError("resource refs must not contain file_path")
            if not isinstance(self.namespace, str) or not _NAMESPACE_RE.fullmatch(self.namespace):
                raise RefError("resource namespace contains unsupported characters")
            if not isinstance(self.resource_id, str) or not _LOCAL_ID_RE.fullmatch(self.resource_id):
                raise RefError("resource id contains unsupported characters")
            if not isinstance(self.pointer_parts, tuple) or not all(isinstance(part, str) for part in self.pointer_parts):
                raise RefError("resource pointer_parts must be a tuple of strings")
            return

        if self.scheme == "file":
            if self.namespace is not None or self.resource_id is not None:
                raise RefError("file refs must not contain resource namespace/id")
            if self.pointer_parts:
                raise RefError("file refs are whole-file only in v0.1")
            if not isinstance(self.file_path, str) or not self.file_path:
                raise RefError("file ref must contain a documentation-relative path")
            if "\\" in self.file_path or "\x00" in self.file_path:
                raise RefError("file ref contains unsupported path characters")
            parts = self.file_path.split("/")
            if any(part in {"", ".", ".."} for part in parts):
                raise RefError("file ref must use non-empty canonical relative path segments")
            path = PurePosixPath(self.file_path)
            if path.is_absolute() or path.as_posix() != self.file_path:
                raise RefError("file ref must be a canonical confined documentation-relative path")
            return

        raise RefError(f"unsupported reference scheme: {self.scheme or '<missing>'}")

    @classmethod
    def parse(cls, value: str) -> "ResourceRef":
        if not isinstance(value, str) or not value:
            raise RefError("reference must be a non-empty string")
        parsed = urlsplit(value)
        if parsed.query:
            raise RefError("resource references do not support query strings")

        if parsed.scheme == "resource":
            namespace = unquote(parsed.netloc)
            path = parsed.path.lstrip("/")
            if not namespace or not path or "/" in path:
                raise RefError("resource ref must be resource://<namespace>/<id>")
            resource_id = unquote(path)
            pointer = unquote(parsed.fragment) if parsed.fragment else ""
            ref = cls(
                scheme="resource",
                namespace=namespace,
                resource_id=resource_id,
                pointer_parts=parse_json_pointer(pointer),
            )
        elif parsed.scheme == "file":
            if parsed.fragment:
                raise RefError("file refs are whole-file only in v0.1; fragments are not supported")
            # The specified syntax is file://architecture/rationale.md, so the URI
            # authority is the first path segment rather than a host.
            joined = "/".join(part for part in (parsed.netloc, parsed.path.lstrip("/")) if part)
            if not joined:
                raise RefError("file ref must contain a documentation-relative path")
            ref = cls(scheme="file", file_path=unquote(joined))
        else:
            raise RefError(f"unsupported reference scheme: {parsed.scheme or '<missing>'}")

        canonical = str(ref)
        if canonical != value:
            raise RefError(f"reference must already be canonical: {canonical!r}")
        return ref

    @classmethod
    def from_resource_id(cls, resource_id: str, pointer: str | None = None) -> "ResourceRef":
        if "." not in resource_id:
            raise RefError("managed resource_id must contain namespace and id separated by '.'")
        namespace, local_id = resource_id.split(".", 1)
        if not namespace or not local_id:
            raise RefError("managed resource_id must contain non-empty namespace and id")
        return cls(
            scheme="resource",
            namespace=namespace,
            resource_id=local_id,
            pointer_parts=parse_json_pointer(pointer),
        )

    @property
    def logical_resource_id(self) -> str | None:
        if self.scheme != "resource":
            return None
        assert self.namespace is not None and self.resource_id is not None
        return f"{self.namespace}.{self.resource_id}"

    @property
    def pointer(self) -> str:
        return format_json_pointer(self.pointer_parts)

    def with_pointer(self, pointer: str) -> "ResourceRef":
        if self.scheme != "resource":
            raise RefError("only structured resource refs may have field pointers")
        return ResourceRef(
            scheme=self.scheme,
            namespace=self.namespace,
            resource_id=self.resource_id,
            pointer_parts=parse_json_pointer(pointer),
        )

    def __str__(self) -> str:
        if self.scheme == "resource":
            assert self.namespace is not None and self.resource_id is not None
            base = f"resource://{quote(self.namespace, safe='-._~')}/{quote(self.resource_id, safe='-._~')}"
            pointer = self.pointer
            return base if not pointer else f"{base}#{quote(pointer, safe='/~')}"
        if self.scheme == "file":
            assert self.file_path is not None
            # Preserve slash separators while URI-escaping path content.
            return "file://" + quote(self.file_path, safe="/-._~")
        raise RefError(f"unsupported reference scheme: {self.scheme}")


FieldRef = ResourceRef


__all__ = [
    "FieldRef",
    "RefError",
    "ResourceRef",
    "format_json_pointer",
    "parse_json_pointer",
]
