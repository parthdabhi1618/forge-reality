import os
import re
import mimetypes
from datetime import datetime
from io import StringIO

try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name, guess_lexer
    from pygments.formatters import HtmlFormatter
    PYGMENTS_AVAILABLE = True
except ImportError:
    PYGMENTS_AVAILABLE = False

C_STYLE_COMMENT_REGEX = r'/[*][\s\S]*?[*]/'

def get_folder_structure(rootdir, ignored_dirs):
    structure = []
    rootdir = os.path.abspath(rootdir)
    for root, dirs, files in os.walk(rootdir):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        level = root.replace(rootdir, '').count(os.sep)
        indent = '  ' * level
        folder_name = os.path.basename(root) if level > 0 else os.path.basename(rootdir)
        if folder_name in ignored_dirs or folder_name.startswith('.'):
            continue
        structure.append(f"{indent}- {folder_name}/")
        subindent = '  ' * (level + 1)
        for f in sorted(files):
            structure.append(f"{subindent}- {f}")
    return '\n'.join(structure)

def is_text_file(file_path):
    text_exts = {'.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.yaml', '.yml',
                 '.md', '.txt', '.html', '.css', '.sh', '.java', '.cpp', '.c', '.h', '.ini', '.cfg', '.toml'}
    ext = os.path.splitext(file_path)[1].lower()
    if ext in text_exts:
        return True
    try:
        mime, _ = mimetypes.guess_type(file_path)
        return mime and mime.startswith('text/')
    except Exception:
        return False

def get_code_language(file_path):
    ext_to_lang = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.tsx': 'tsx', '.jsx': 'jsx', '.json': 'json',
        '.yaml': 'yaml', '.yml': 'yaml', '.md': 'markdown',
        '.html': 'html', '.css': 'css', '.sh': 'bash',
        '.java': 'java', '.cpp': 'cpp', '.c': 'c', '.h': 'c',
        '.ini': 'ini', '.cfg': 'ini', '.toml': 'toml'
    }
    return ext_to_lang.get(os.path.splitext(file_path)[1].lower(), '')

def llm_friendly_minify(content: str) -> str:
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(r'#.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(C_STYLE_COMMENT_REGEX, '', content)
    lines = [line.rstrip() for line in content.splitlines()]
    non_empty_lines = []
    in_blank_sequence = False
    for line in lines:
        if not line.strip():
            if not in_blank_sequence:
                non_empty_lines.append(line)
                in_blank_sequence = True
        else:
            non_empty_lines.append(line)
            in_blank_sequence = False
    return '\n'.join(non_empty_lines).strip()

def llm_stripped_minify(content: str, lang: str) -> str:
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(r'#.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(C_STYLE_COMMENT_REGEX, '', content, flags=re.DOTALL)
    lines = [line.rstrip() for line in content.splitlines() if line.strip()]
    content = '\n'.join(lines)
    content = re.sub(r'\s+([{};,()=+\-\*\/?:])\s*', r'\1', content)
    content = re.sub(r'\s+', ' ', content)
    if lang in ('tsx', 'jsx', 'ts', 'js', 'html'):
        content = re.sub(r'>\s+<', '><', content)
        content = re.sub(r'\s*/>', '/>', content)
    return content.strip()

# --- Content Generation Functions ---

def generate_markdown_content(folder, ignored_dirs, conv, compressed=False):
    string_io = StringIO()
    abs_folder = os.path.abspath(folder)
    string_io.write(f"# Project Summary (Fresh read - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n\n")
    string_io.write(f"**Reading from**: `{abs_folder}`\n\n")
    string_io.write("## Structure\n```\n")
    string_io.write(get_folder_structure(abs_folder, ignored_dirs))
    string_io.write("\n```\n\n")
    string_io.write("## Files\n\n")
    for root, dirs, files in os.walk(abs_folder):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        for file in sorted(files):
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, abs_folder)
            string_io.write(f"### {rel_path}\n")
            if is_text_file(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        raw = f.read()
                    lang = get_code_language(full_path)
                    stripped = llm_stripped_minify(raw, lang) if compressed else llm_friendly_minify(raw)
                    string_io.write(f"```{lang}\n{stripped}\n```\n\n")
                except Exception as e:
                    string_io.write(f"<!-- Error reading file: {e} -->\n\n")
            elif DOCLING_AVAILABLE and conv:
                try:
                    doc = conv.convert(full_path)
                    string_io.write(doc.to_markdown())
                    string_io.write("\n\n")
                except Exception as e:
                    string_io.write(f"<!-- Docling failed to convert non-text file: {e} -->\n\n")
            else:
                string_io.write(f"<!-- Skipped non-text file -->\n\n")
    return string_io.getvalue()

def generate_html_content(folder, ignored_dirs, conv):
    abs_folder = os.path.abspath(folder)
    formatter = HtmlFormatter(style='monokai', full=True, cssclass="highlight")
    html_head = f"""<!DOCTYPE html>
<html>
<head>
<title>Project Summary: {os.path.basename(abs_folder)}</title>
<style>
{formatter.get_style_defs()}
body {{ font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0; background: #0F172A; color: #E2E8F0; }}
.container {{ max-width: 1200px; margin: 2rem auto; padding: 2rem; background: #1E293B; border-radius: 8px; }}
h1, h2, h3 {{ color: #60A5FA; border-bottom: 1px solid #334155; padding-bottom: 0.5rem;}}
h1 {{ font-size: 2.5em; }}
h2 {{ font-size: 2em; }}
h3 {{ font-size: 1.5em; }}
code {{ background: #282c34; padding: 2px 4px; border-radius: 4px; font-family: 'Fira Code', monospace;}}
pre {{ white-space: pre-wrap; word-wrap: break-word; }}
.highlight {{ border-radius: 8px; margin-bottom: 1rem; }}
.file-block {{ border: 1px solid #334155; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; background: #0F172A; }}
.error {{ color: #F87171; background: #450A0A; padding: 1rem; border-radius: 4px; }}
</style>
</head>
<body>
<div class="container">
<h1>Project Summary</h1>
<p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<p><strong>From:</strong> <code>{abs_folder}</code></p>
"""
    structure_html = f"<h2>Project Structure</h2><pre><code>{get_folder_structure(abs_folder, ignored_dirs)}</code></pre>"
    files_html = ["<h2>Files</h2>"]
    for root, dirs, files in os.walk(abs_folder):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]
        for file in sorted(files):
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, abs_folder)
            files_html.append(f"<div class='file-block'><h3>{rel_path}</h3>")
            if is_text_file(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        raw = f.read()
                    if PYGMENTS_AVAILABLE:
                        lang = get_code_language(full_path)
                        try:
                            lexer = get_lexer_by_name(lang) if lang else guess_lexer(raw)
                            files_html.append(highlight(raw, lexer, formatter))
                        except Exception:
                            files_html.append(f"<pre><code>{raw}</code></pre>")
                    else:
                        files_html.append(f"<pre><code>{raw}</code></pre>")
                except Exception as e:
                    files_html.append(f"<p class='error'>Error reading file: {e}</p>")
            else:
                 files_html.append("<p><em>Skipped non-text file.</em></p>")
            files_html.append("</div>")
    html_foot = "</div></body></html>"
    return html_head + structure_html + "".join(files_html) + html_foot


class ContextGenerator:
    def __init__(self):
        self.ignored_dirs = {
            'node_modules', 'venv', '.venv', 'env', '__pycache__', '.git',
            'dist', 'build', 'target', '.next', 'coverage', '.idea', '.vscode',
            'bin', 'obj', 'tmp', 'temp', '.cache', '.pytest_cache'
        }
        self.conv = DocumentConverter() if DOCLING_AVAILABLE else None

    def generate_context_from_folder(self, folder_path, output_format='html'):
        if not os.path.isdir(folder_path):
            raise ValueError("Invalid folder path provided.")
        
        if output_format == 'html':
            return generate_html_content(folder_path, self.ignored_dirs, self.conv)
        elif output_format == 'md-compressed':
            return generate_markdown_content(folder_path, self.ignored_dirs, self.conv, compressed=True)
        else: # Default to 'md-friendly'
            return generate_markdown_content(folder_path, self.ignored_dirs, self.conv, compressed=False)
