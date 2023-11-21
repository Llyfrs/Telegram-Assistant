import os
import re


def load_file(filename: str):
    if not filename.endswith(".py") and not filename.endswith(".txt") and not filename.endswith(".md"):
        return "Invalid file type"

    file_path = "files/" + filename

    with open(file_path, "r") as f:
        return f.read()


def create_file(filename: str):
    if not filename.endswith(".py") and not filename.endswith(".txt") and not filename.endswith(".md"):
        return "Invalid file type"

    file_path = "files/" + filename

    with open(file_path, "w") as f:
        f.write("")

    return "File created"


def save_file(filename: str, content: str):
    if filename not in os.listdir("files"):
        return "File not found"

    if not filename.endswith(".py") and not filename.endswith(".txt") and not filename.endswith(".md"):
        return "Invalid file type"

    file_path = "files/" + filename

    with open(file_path, "w") as f:
        f.write(content)

    return "File saved"


def delete_file(filename: str):
    if not filename.endswith(".py") and not filename.endswith(".txt") and not filename.endswith(".md"):
        return "Invalid file type"

    file_path = "files/" + filename

    os.remove(file_path)

    return "File deleted"


def get_sections(filename: str):
    if not filename.endswith(".md"):
        return "Sections are only available for markdown files"

    file_path = "files/" + filename

    with open(file_path, "r") as f:
        content = f.read()

    sections = re.findall(r'^##\s+(.+)$', content, flags=re.MULTILINE)

    return "\n".join(sections)


def get_section(filename: str, section: str):
    if not filename.endswith(".md"):
        return "Sections are only available for markdown files"

    file_path = "files/" + filename

    with open(file_path, "r") as f:
        content = f.read()

    # Use a non-greedy quantifier (*?) to capture everything between the specified section and the next section
    section_pattern = re.compile(r'^##\s+' + re.escape(section) + r'\s+(.+?)(?=(?:^##\s+|\Z))',
                                 flags=re.MULTILINE | re.DOTALL)
    section_match = section_pattern.search(content)

    if not section_match:
        return "Section not found"

    return section_match.group(1).strip()


def save_section(filename: str, section: str, content: str):
    if not filename.endswith(".md"):
        return "Sections are only available for markdown files"

    file_path = "files/" + filename

    with open(file_path, "r") as f:
        file_content = f.read()

    # Use a non-greedy quantifier (*?) to capture everything between the specified section and the next section
    section_pattern = re.compile(r'^##\s+' + re.escape(section) + r'\s+(.+?)(?=(?:^##\s+|\Z))',
                                 flags=re.MULTILINE | re.DOTALL)

    file_content = section_pattern.sub(f"## {section}\n\n{content}\n\n", file_content)

    with open(file_path, "w") as f:
        f.write(file_content)

    return "Section saved"


def add_section(filename: str, section: str, content: str):
    if not filename.endswith(".md"):
        return "Sections are only available for markdown files"

    file_path = "files/" + filename

    with open(file_path, "r") as f:
        file_content = f.read()

    file_content += f"\n\n## {section}\n\n{content}\n\n"

    with open(file_path, "w") as f:
        f.write(file_content)

    return "Section added"


def list_files():
    files = os.listdir("files")
    return "Files:\n" + "\n".join(files)


# Create directory if it doesn't exist
if not os.path.exists("files"):
    os.makedirs("files")

# print(get_sections("test.md"))
# print(get_section("test.md", "Test2"))
# print(save_section("test.md", "Test2", "Test2 this is saved section and I like it "))
# print(add_section("test.md", "Test3", "Test3 this is Inserted section and I like it "))
