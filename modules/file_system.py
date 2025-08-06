import os

class InMemoryFileSystem:
    def __init__(self):
        self.fs = {}

    def _get_node(self, path, create_missing=False, is_dir=False):
        if path == "/":
            return self.fs
        parts = [p for p in path.strip("/").split("/") if p]
        node = self.fs
        for i, part in enumerate(parts):
            if part not in node:
                if create_missing:
                    node[part] = {} if (is_dir or i < len(parts)-1) else ""
                else:
                    raise FileNotFoundError(f"Path not found: {'/'.join(parts[:i+1])}")
            node = node[part]
            if isinstance(node, str) and (i < len(parts)-1 or is_dir):
                raise NotADirectoryError(f"Expected directory at: {'/'.join(parts[:i+1])}")
        return node

    def mkdir(self, path : str):
        try:
            self._get_node(path, create_missing=True, is_dir=True)
            return "OK"
        except Exception as e:
            return str(e)

    def create_file(self, path : str, content=""):
        try:
            if path.endswith("/"):
                return "File path cannot end with '/'"
            parts = path.strip("/").split("/")
            dir_path = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"
            filename = parts[-1]
            dir_node = self._get_node(dir_path, create_missing=True, is_dir=True)
            if filename in dir_node and isinstance(dir_node[filename], dict):
                return f"{path} is a directory"
            dir_node[filename] = content
            return "OK"
        except Exception as e:
            return str(e)

    def read_file(self, path : str):
        try:
            node = self._get_node(path)
            if isinstance(node, dict):
                return f"{path} is a directory"
            return node
        except Exception as e:
            return str(e)

    def write_file(self, path : str, content : str, append : bool = False):
        try:
            node = self._get_node(path)
            if isinstance(node, dict):
                return f"{path} is a directory"
            parts = path.strip("/").split("/")
            dir_path = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"
            filename = parts[-1]
            dir_node = self._get_node(dir_path)
            if append:
                dir_node[filename] += content
            else:
                dir_node[filename] = content
            return "OK"
        except Exception as e:
            return str(e)

    def delete(self, path : str):
        try:
            if path == "/":
                return "Cannot delete root"
            parts = path.strip("/").split("/")
            parent_path = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"
            name = parts[-1]
            parent = self._get_node(parent_path)
            if name not in parent:
                return f"{path} not found"
            del parent[name]
            return "OK"
        except Exception as e:
            return str(e)

    def list_dir(self, path: str):
        try:
            if path == ".":
                path = "/"
            node = self._get_node(path)
            if isinstance(node, str):
                return f"{path} is a file"
            return list(node.keys())
        except Exception as e:
            return str(e)

    def save_to_disk(self, target_folder):
        try:
            def recurse(node, current_path):
                for name, child in node.items():
                    child_path = os.path.join(current_path, name)
                    if isinstance(child, dict):
                        os.makedirs(child_path, exist_ok=True)
                        recurse(child, child_path)
                    else:
                        with open(child_path, "w", encoding="utf-8") as f:
                            f.write(child)
            os.makedirs(target_folder, exist_ok=True)
            recurse(self.fs, target_folder)
            return "OK"
        except Exception as e:
            return str(e)

    def __str__(self):
        def recurse(node, prefix):
            lines = []
            for name, child in node.items():
                if isinstance(child, dict):
                    lines.append(f"{prefix}{name}/")
                    lines.extend(recurse(child, prefix + "  "))
                else:
                    lines.append(f"{prefix}{name}")
            return lines
        return "\n".join(recurse(self.fs, ""))
