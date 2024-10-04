import re
from modules.database import ValkeyDB

key_header = "files:"

def load_file(filename: str):
    if not filename.endswith(".py") and not filename.endswith(".txt") and not filename.endswith(".md"):
        return "Invalid file type"

    file_path = key_header + filename

    content = ValkeyDB().get_serialized(file_path)
    if content is None:
        return "File not found"

    return content


def create_file(filename: str):
    if not filename.endswith(".py") and not filename.endswith(".txt") and not filename.endswith(".md"):
        return "Invalid file type"

    file_path = key_header + filename

    ValkeyDB().set_serialized(file_path, " ")

    return "File created"


def save_file(filename: str, content: str):
    if not filename.endswith(".py") and not filename.endswith(".txt") and not filename.endswith(".md"):
        return "Invalid file type"

    file_path = key_header + filename

    ValkeyDB().set_serialized(file_path, content)

    return "File saved"


def delete_file(filename: str):
    if not filename.endswith(".py") and not filename.endswith(".txt") and not filename.endswith(".md"):
        return "Invalid file type"

    file_path = key_header + filename

    ValkeyDB().delete(file_path)

    return "File deleted"


def get_sections(filename: str):
    if not filename.endswith(".md"):
        return "Sections are only available for markdown files"

    file_path = key_header + filename

    content = ValkeyDB().get_serialized(file_path)
    if content is None:
        return "File not found"

    sections = re.findall(r'^##\s+(.+)$', content, flags=re.MULTILINE)

    return "\n".join(sections)


def get_section(filename: str, section: str):
    if not filename.endswith(".md"):
        return "Sections are only available for markdown files"

    file_path = key_header + filename

    content = ValkeyDB().get_serialized(file_path)
    if content is None:
        return "File not found"

    section_pattern = re.compile(r'^##\s+' + re.escape(section) + r'\s+(.+?)(?=(?:^##\s+|\Z))',
                                 flags=re.MULTILINE | re.DOTALL)
    section_match = section_pattern.search(content)

    if not section_match:
        return "Section not found"

    return section_match.group(1).strip()


def save_section(filename: str, section: str, content: str):
    if not filename.endswith(".md"):
        return "Sections are only available for markdown files"

    file_path = key_header + filename

    file_content = ValkeyDB().get_serialized(file_path)
    if file_content is None:
        return "File not found"

    section_pattern = re.compile(r'^##\s+' + re.escape(section) + r'\s+(.+?)(?=(?:^##\s+|\Z))',
                                 flags=re.MULTILINE | re.DOTALL)

    updated_content = section_pattern.sub(f"## {section}\n\n{content}\n\n", file_content)

    ValkeyDB().set_serialized(file_path, updated_content)

    return "Section saved"


def add_section(filename: str, section: str, content: str):
    if not filename.endswith(".md"):
        return "Sections are only available for markdown files"

    file_path = key_header + filename

    file_content = ValkeyDB().get_serialized(file_path)

    if file_content is None:
        return "File not found"

    file_content += f"\n\n## {section}\n\n{content}\n\n"

    ValkeyDB().set_serialized(file_path, file_content)

    return "Section added"

def run_python_file(filename: str):
    if not filename.endswith(".py"):
        return "Only python files can be executed"

    file_path = key_header + filename

    content = ValkeyDB().get_serialized(file_path)
    if content is None:
        return "File not found"

    try:
        exec(content)
    except Exception as ex:
        return f"Error: {ex}"

    return "File executed"

def list_files():
    files = ValkeyDB().list(key_header)
    files = [file[len(key_header):] for file in files]
    return "\n".join(files)




