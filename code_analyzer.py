# code_analyzer.py
"""
Code Analyzer - Đọc sâu code từ GitHub repo
- Clone repo
- Đọc tất cả file code
- Extract functions, classes, imports
- Detect code smells
"""
import os
import re
import shutil
import tempfile
import subprocess
from pathlib import Path


class CodeAnalyzer:
    """Phân tích code sâu từ GitHub repo"""

    # Ngôn ngữ hỗ trợ
    CODE_EXTENSIONS = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".sql": "sql",
        ".sh": "shell",
    }

    # File/folder cần bỏ qua
    IGNORE_PATTERNS = [
        ".git", "node_modules", "__pycache__", "venv", ".venv",
        "dist", "build", ".idea", ".vscode", "target",
        "coverage", ".pytest_cache", ".mypy_cache",
    ]

    # File cần bỏ qua
    IGNORE_FILES = [
        "package-lock.json", "yarn.lock", "poetry.lock",
        "Pipfile.lock", ".gitignore", ".DS_Store",
    ]

    MAX_FILES = 20           # Max files để đọc
    MAX_FILE_SIZE = 10000    # Max ký tự/file
    MAX_TOTAL_SIZE = 50000   # Max tổng

    def __init__(self):
        self.temp_dir = None

    def analyze_github_repo(self, url):
        """
        Clone repo GitHub và phân tích.
        Returns:
            dict: {
                "language": str,
                "files": [{"path": str, "content": str}],
                "functions": [str],
                "classes": [str],
                "imports": [str],
                "total_lines": int,
                "errors": [str],
            }
        """
        # Parse URL
        match = re.match(r"https?://github\.com/([^/]+)/([^/\s?#]+)", url)
        if not match:
            return self._empty_result()

        owner = match.group(1)
        repo = match.group(2).replace(".git", "")
        clone_url = f"https://github.com/{owner}/{repo}.git"

        # Tạo temp dir
        self.temp_dir = tempfile.mkdtemp(prefix="cognicraft_code_")

        try:
            # Clone repo (shallow clone để nhanh)
            print(f"[CodeAnalyzer] Cloning {owner}/{repo}...")
            result = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, self.temp_dir],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                print(f"[CodeAnalyzer] Clone failed: {result.stderr[:200]}")
                return self._empty_result()

            # Phân tích
            return self._scan_repo()

        except subprocess.TimeoutExpired:
            print(f"[CodeAnalyzer] Clone timeout")
            return self._empty_result()
        except Exception as e:
            print(f"[CodeAnalyzer] Error: {e}")
            return self._empty_result()
        finally:
            self._cleanup()

    def _scan_repo(self):
        """Scan repo và extract code"""
        files = []
        functions = []
        classes = []
        imports = []
        total_lines = 0
        total_size = 0
        main_language = None
        language_count = {}

        repo_path = Path(self.temp_dir)

        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip ignored
            if any(ig in str(file_path) for ig in self.IGNORE_PATTERNS):
                continue
            if file_path.name in self.IGNORE_FILES:
                continue

            # Check extension
            ext = file_path.suffix.lower()
            if ext not in self.CODE_EXTENSIONS:
                continue

            # Check size
            if len(files) >= self.MAX_FILES:
                break
            if total_size >= self.MAX_TOTAL_SIZE:
                break

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    continue

                # Truncate nếu quá dài
                if len(content) > self.MAX_FILE_SIZE:
                    content = content[:self.MAX_FILE_SIZE] + "\n[... truncated ...]"

                # Relative path
                rel_path = str(file_path.relative_to(repo_path))

                # Extract language
                lang = self.CODE_EXTENSIONS[ext]
                language_count[lang] = language_count.get(lang, 0) + 1

                # Extract functions, classes, imports
                self._extract_symbols(content, lang, functions, classes, imports)

                # Count lines
                lines = content.count("\n") + 1
                total_lines += lines
                total_size += len(content)

                files.append({
                    "path": rel_path,
                    "language": lang,
                    "content": content,
                    "lines": lines,
                })

            except Exception as e:
                print(f"[CodeAnalyzer] Read error {file_path}: {e}")
                continue

        # Determine main language
        if language_count:
            main_language = max(language_count, key=language_count.get)

        # Detect code smells
        errors = self._detect_smells(files)

        print(f"[CodeAnalyzer] Analyzed {len(files)} files, {total_lines} lines")
        print(f"[CodeAnalyzer] Main language: {main_language}")
        print(f"[CodeAnalyzer] Found {len(functions)} functions, {len(classes)} classes")

        return {
            "language": main_language or "unknown",
            "files": files,
            "functions": functions[:50],    # Limit
            "classes": classes[:30],
            "imports": list(set(imports))[:30],
            "total_lines": total_lines,
            "errors": errors,
        }

    def _extract_symbols(self, content, language, functions, classes, imports):
        """Extract functions, classes, imports từ code"""
        try:
            if language == "python":
                # Python functions
                for m in re.finditer(r"^\s*def\s+(\w+)\s*\(", content, re.MULTILINE):
                    functions.append(m.group(1))
                # Python classes
                for m in re.finditer(r"^\s*class\s+(\w+)", content, re.MULTILINE):
                    classes.append(m.group(1))
                # Python imports
                for m in re.finditer(r"^\s*(?:from\s+(\S+)\s+)?import\s+(.+)", content, re.MULTILINE):
                    imports.append(m.group(0).strip()[:80])

            elif language in ["javascript", "typescript"]:
                # JS functions
                for m in re.finditer(r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?(?:\(|function))", content):
                    name = m.group(1) or m.group(2)
                    if name:
                        functions.append(name)
                # JS classes
                for m in re.finditer(r"class\s+(\w+)", content):
                    classes.append(m.group(1))
                # JS imports
                for m in re.finditer(r"^import\s+.+$", content, re.MULTILINE):
                    imports.append(m.group(0).strip()[:80])

            elif language == "java":
                for m in re.finditer(r"(?:public|private|protected)?\s*(?:static\s+)?(?:\w+)\s+(\w+)\s*\(", content):
                    functions.append(m.group(1))
                for m in re.finditer(r"class\s+(\w+)", content):
                    classes.append(m.group(1))

            elif language == "cpp" or language == "c":
                for m in re.finditer(r"(?:\w+)\s+(\w+)\s*\([^)]*\)\s*\{", content):
                    functions.append(m.group(1))
                for m in re.finditer(r"class\s+(\w+)", content):
                    classes.append(m.group(1))
                for m in re.finditer(r"#include\s+[<\"]([^>\"]+)[>\"]", content):
                    imports.append(m.group(1))

        except Exception as e:
            print(f"[CodeAnalyzer] Extract error: {e}")

    def _detect_smells(self, files):
        """Detect code smells đơn giản"""
        errors = []

        for f in files:
            content = f["content"]
            path = f["path"]

            # TODO comments
            todos = re.findall(r"#\s*TODO:?\s*(.+)", content, re.IGNORECASE)
            todos += re.findall(r"//\s*TODO:?\s*(.+)", content)
            for t in todos[:3]:
                errors.append(f"[{path}] TODO: {t.strip()[:80]}")

            # FIXME comments
            fixmes = re.findall(r"#\s*FIXME:?\s*(.+)", content, re.IGNORECASE)
            fixmes += re.findall(r"//\s*FIXME:?\s*(.+)", content)
            for fx in fixmes[:3]:
                errors.append(f"[{path}] FIXME: {fx.strip()[:80]}")

            # Hardcoded credentials
            if re.search(r"(?:password|api_key|secret)\s*=\s*['\"][^'\"]+['\"]", content, re.IGNORECASE):
                errors.append(f"[{path}] Possible hardcoded credential")

            # Bare except (Python)
            if f["language"] == "python":
                if re.search(r"except\s*:", content):
                    errors.append(f"[{path}] Bare 'except:' (nên catch specific exception)")

            # Print statements trong production
            if f["language"] == "python":
                prints = len(re.findall(r"^\s*print\s*\(", content, re.MULTILINE))
                if prints > 10:
                    errors.append(f"[{path}] {prints} print statements (nên dùng logging)")

        return errors[:10]

    def _cleanup(self):
        """Xóa temp dir"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"[CodeAnalyzer] Cleanup error: {e}")
        self.temp_dir = None

    def _empty_result(self):
        return {
            "language": "unknown",
            "files": [],
            "functions": [],
            "classes": [],
            "imports": [],
            "total_lines": 0,
            "errors": [],
        }

    def build_content_for_ai(self, analysis):
        """Build content string để gửi AI"""
        if not analysis["files"]:
            return ""

        parts = [f"=== GITHUB REPO ANALYSIS ==="]
        parts.append(f"Language: {analysis['language']}")
        parts.append(f"Total lines: {analysis['total_lines']}")
        parts.append(f"Files: {len(analysis['files'])}")
        parts.append(f"Functions: {len(analysis['functions'])}")
        parts.append(f"Classes: {len(analysis['classes'])}")

        if analysis["imports"]:
            parts.append(f"\nImports: {', '.join(analysis['imports'][:10])}")

        if analysis["errors"]:
            parts.append(f"\n=== CODE SMELLS ===")
            for err in analysis["errors"]:
                parts.append(f"- {err}")

        parts.append(f"\n=== CODE FILES ===")
        for f in analysis["files"]:
            parts.append(f"\n--- File: {f['path']} ({f['language']}, {f['lines']} lines) ---")
            parts.append(f["content"])

        return "\n".join(parts)