import re
import shutil
from pathlib import Path
from typing import Optional


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

    def read_file(self, path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> str:
        """Read file contents with line numbers. Use offset/limit for large files."""
        try:
            target = self._resolve_path(path)
            if not target.exists():
                return f"Error: {path} not found"
            if target.is_dir():
                return f"Error: {path} is a directory"

            all_lines = target.read_text(encoding="utf-8").splitlines()
            total = len(all_lines)

            start = 0
            if offset is not None:
                start = max(0, offset - 1)

            end = total
            if limit is not None:
                end = min(total, start + limit)

            selected = all_lines[start:end]
            numbered = [f"{start + i + 1:>6}|{line}" for i, line in enumerate(selected)]
            result = "\n".join(numbered)

            shown = len(selected)
            if shown < total:
                result += f"\n[Read {shown} lines (lines {start + 1}-{end}) out of {total} total]"

            return result
        except Exception as e:
            return f"Error: {e}"

    def write_file(self, path: str, content: str) -> str:
        """Create or overwrite a file. Parent directories are created automatically."""
        try:
            target = self._resolve_path(path)
            if target.exists() and target.is_dir():
                return f"Error: {path} is a directory"

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return "OK"
        except Exception as e:
            return f"Error: {e}"

    def str_replace(self, path: str, old_str: str, new_str: str) -> str:
        """Replace an exact string occurrence in a file.
        
        old_str must match exactly one location in the file. Include surrounding
        lines in old_str to make it unique if there are multiple matches.
        """
        try:
            target = self._resolve_path(path)
            if not target.exists():
                return f"Error: {path} not found"
            if target.is_dir():
                return f"Error: {path} is a directory"

            content = target.read_text(encoding="utf-8")

            count = content.count(old_str)
            if count == 0:
                return (
                    "Error: No match found. The old_str was not found in the file. "
                    "Make sure it matches the file content exactly, including whitespace and indentation."
                )
            if count > 1:
                return (
                    f"Error: Multiple matches found ({count} occurrences). "
                    "Include more surrounding context in old_str to make it unique."
                )

            new_content = content.replace(old_str, new_str, 1)
            target.write_text(new_content, encoding="utf-8")

            new_lines = new_content.splitlines()
            replacement_start = new_content.find(new_str)
            line_num = new_content[:replacement_start].count("\n")

            context_before = max(0, line_num - 2)
            new_str_line_count = new_str.count("\n") + 1
            context_after = min(len(new_lines), line_num + new_str_line_count + 2)

            snippet_lines = new_lines[context_before:context_after]
            numbered = [f"{context_before + i + 1:>6}|{line}" for i, line in enumerate(snippet_lines)]

            return "OK\n" + "\n".join(numbered)
        except Exception as e:
            return f"Error: {e}"

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

    def move(self, src: str, dest: str):
        """Move or rename a file or directory."""
        try:
            src_path = self._resolve_path(src)
            dest_path = self._resolve_path(dest)

            if not src_path.exists():
                return f"{src} not found"

            if src_path == self.root:
                return "Cannot move root"

            # Ensure destination parent exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(src_path), str(dest_path))
            return "OK"
        except Exception as e:
            return str(e)

    def copy(self, src: str, dest: str):
        """Copy a file or directory."""
        try:
            src_path = self._resolve_path(src)
            dest_path = self._resolve_path(dest)

            if not src_path.exists():
                return f"{src} not found"

            # Ensure destination parent exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dest_path))
            else:
                shutil.copy2(str(src_path), str(dest_path))
            return "OK"
        except Exception as e:
            return str(e)

    def list_dir(self, path: str = "") -> str:
        """List files and directories at the given path with type indicators and sizes."""
        try:
            if path == ".":
                path = ""
            target = self._resolve_path(path)

            if not target.exists():
                return f"Error: {path or '/'} not found"
            if not target.is_dir():
                return f"Error: {path} is not a directory"

            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            lines = []
            for entry in entries:
                if entry.is_dir():
                    lines.append(f"  {entry.name}/")
                else:
                    size = entry.stat().st_size
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    lines.append(f"  {entry.name}  ({size_str})")

            if not lines:
                return "Directory is empty."
            return "\n".join(lines)
        except Exception as e:
            return f"Error: {e}"

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

    def tree(self) -> str:
        """Show the full directory tree from the root."""
        return str(self)

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
