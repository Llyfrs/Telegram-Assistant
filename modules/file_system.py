import os
import re
import shlex
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

    def shell(self, command: str):
        """Execute a shell-style file system command.
        
        Supported commands:
            mkdir <path>           - Create directory
            ls [path]              - List directory contents
            cat <path>             - Read file contents
            rm <path>              - Delete file or directory
            touch <path>           - Create empty file
            echo <content> > <path>  - Write to file
            echo <content> >> <path> - Append to file
            mv <src> <dest>        - Move/rename file or directory
            cp <src> <dest>        - Copy file or directory
            tree                   - Show directory tree
            find <query>           - Search files by name or content
        """
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return f"Parse error: {e}"

        if not parts:
            return "No command provided"

        cmd = parts[0].lower()
        args = parts[1:]

        # Handle echo with redirection specially
        if cmd == "echo":
            return self._handle_echo(command)

        # Route to appropriate method
        if cmd == "mkdir":
            if not args:
                return "mkdir: missing path"
            return self.mkdir(args[0])

        elif cmd == "ls":
            path = args[0] if args else ""
            return self.list_dir(path)

        elif cmd == "cat":
            if not args:
                return "cat: missing path"
            return self.read_file(args[0])

        elif cmd == "rm":
            if not args:
                return "rm: missing path"
            return self.delete(args[0])

        elif cmd == "touch":
            if not args:
                return "touch: missing path"
            return self.create_file(args[0], "")

        elif cmd == "mv":
            if len(args) < 2:
                return "mv: missing source or destination"
            return self.move(args[0], args[1])

        elif cmd == "cp":
            if len(args) < 2:
                return "cp: missing source or destination"
            return self.copy(args[0], args[1])

        elif cmd == "tree":
            return str(self)

        elif cmd == "find":
            if not args:
                return "find: missing query"
            return self.search(args[0])

        else:
            return f"Unknown command: {cmd}. Supported: mkdir, ls, cat, rm, touch, echo, mv, cp, tree, find"

    def _handle_echo(self, command: str):
        """Handle echo command with > or >> redirection."""
        # Check for append (>>)
        if ">>" in command:
            parts = command.split(">>", 1)
            append = True
        elif ">" in command:
            parts = command.split(">", 1)
            append = False
        else:
            return "echo: missing redirection (> or >>)"

        if len(parts) != 2:
            return "echo: invalid syntax"

        # Extract content from echo part (remove 'echo ' prefix)
        echo_part = parts[0].strip()
        if not echo_part.lower().startswith("echo "):
            return "echo: invalid syntax"
        
        content = echo_part[5:].strip()
        
        # Remove surrounding quotes if present
        if (content.startswith('"') and content.endswith('"')) or \
           (content.startswith("'") and content.endswith("'")):
            content = content[1:-1]

        # Get the file path
        file_path = parts[1].strip()
        if not file_path:
            return "echo: missing file path"

        return self.write_file(file_path, content, append=append)

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
