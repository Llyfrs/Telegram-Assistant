import os
import re
import shutil
from pathlib import Path


class DiskFileSystem:
    def __init__(self, root_dir="storage"):
        self.root = Path(root_dir).resolve()
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the root and ensure it's safe."""
        # Clean path
        path = path.strip().strip("/")
        if not path:
            return self.root

        target_path = (self.root / path).resolve()

        # Security check: prevent directory traversal
        if not str(target_path).startswith(str(self.root)):
            raise ValueError(f"Access denied: {path} is outside sandbox.")

        return target_path

    def mkdir(self, path: str):
        try:
            target = self._resolve_path(path)
            if target.exists() and not target.is_dir():
                return f"{path} exists and is not a directory"
            target.mkdir(parents=True, exist_ok=True)
            return "OK"
        except Exception as e:
            return str(e)

    def create_file(self, path: str, content=""):
        """Creates a new file. If it exists, it overwrites it."""
        return self.write_file(path, content)

    def read_file(self, path: str):
        try:
            target = self._resolve_path(path)
            if not target.exists():
                return f"{path} not found"
            if target.is_dir():
                return f"{path} is a directory"
            return target.read_text(encoding="utf-8")
        except Exception as e:
            return str(e)

    def write_file(self, path: str, content: str, append: bool = False):
        try:
            target = self._resolve_path(path)
            if target.exists() and target.is_dir():
                return f"{path} is a directory"

            # Ensure parent directory exists
            target.parent.mkdir(parents=True, exist_ok=True)

            mode = "a" if append else "w"
            with open(target, mode, encoding="utf-8") as f:
                f.write(content)
            return "OK"
        except Exception as e:
            return str(e)

    def delete(self, path: str):
        """Delete a file or directory at the given path.
        Deleting a directory will remove it and all its contents."""
        try:
            target = self._resolve_path(path)
            if target == self.root:
                return "Cannot delete root"

            if not target.exists():
                return f"{path} not found"

            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return "OK"
        except Exception as e:
            return str(e)

    def list_dir(self, path: str):
        """List files and directories in the given path / folder."""
        try:
            if path == ".":
                path = ""
            target = self._resolve_path(path)
            
            if not target.exists():
                return f"{path} not found"
            if not target.is_dir():
                return f"{path} is a file"

            # List relative names
            return [p.name for p in target.iterdir()]
        except Exception as e:
            return str(e)

    def search(self, query: str, case_sensitive: bool = False, regex: bool = False):
        try:
            results = []
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(query if regex else re.escape(query), flags)

            for path in self.root.rglob("*"):
                # Check filename
                try:
                    rel_path = path.relative_to(self.root)
                except ValueError:
                    continue
                    
                if pattern.search(path.name):
                    results.append({
                        "match_in": "filename",
                        "file": str(rel_path)
                    })

                # Check content if it's a file
                if path.is_file():
                    try:
                        content = path.read_text(encoding="utf-8")
                        for i, line in enumerate(content.splitlines(), start=1):
                            if pattern.search(line):
                                results.append({
                                    "match_in": "content",
                                    "file": str(rel_path),
                                    "line_number": i,
                                    "line": line.strip()
                                })
                    except (UnicodeDecodeError, PermissionError):
                        pass 

            return results

        except Exception as e:
            return str(e)

    def __str__(self):
        def recurse(dir_path: Path, prefix: str):
            lines = []
            try:
                children = sorted(list(dir_path.iterdir()), key=lambda p: (not p.is_dir(), p.name.lower()))
                for child in children:
                    if child.is_dir():
                        lines.append(f"{prefix}{child.name}/")
                        lines.extend(recurse(child, prefix + "  "))
                    else:
                        lines.append(f"{prefix}{child.name}")
            except PermissionError:
                lines.append(f"{prefix}<Permission Denied>")
            return lines

        return "\n".join(recurse(self.root, ""))
