# store/backend/security.py
"""
Security Scanner cho plugins/themes
- Quét mã độc trong .cogni packages
- Block dangerous patterns
- Quét CSS themes cho XSS/import
- Tích hợp với Switch Board sandbox
"""
import os
import re
import zipfile
import tempfile
import hashlib
import json
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone


# ============================================================
# MALWARE PATTERNS — Python
# ============================================================
DANGEROUS_PYTHON_PATTERNS = [
    # Command execution
    (r'\bexec\s*\(', 'exec()', 'critical'),
    (r'\beval\s*\(', 'eval()', 'critical'),
    (r'\b__import__\s*\(', '__import__()', 'critical'),
    (r'\bcompile\s*\(', 'compile()', 'critical'),
    (r'\bexecfile\s*\(', 'execfile()', 'critical'),

    # System calls
    (r'\bos\.system\s*\(', 'os.system()', 'critical'),
    (r'\bos\.popen\s*\(', 'os.popen()', 'critical'),
    (r'\bos\.exec[lv]p?e?\s*\(', 'os.exec*()', 'critical'),
    (r'\bos\.spawn\w*\s*\(', 'os.spawn*()', 'critical'),
    (r'\bos\.fork\s*\(', 'os.fork()', 'critical'),
    (r'\bsubprocess\.\w+', 'subprocess.*', 'critical'),
    (r'\bpty\.spawn\s*\(', 'pty.spawn()', 'critical'),
    (r'\bctypes\.\w+', 'ctypes.*', 'high'),

    # Network — phoning home
    (r'\bsocket\.socket\s*\(', 'socket.socket()', 'critical'),
    (r'\bsocket\.create_connection', 'socket.create_connection', 'critical'),
    (r'\burllib\.request\.urlopen', 'urllib.request.urlopen', 'high'),
    (r'\burllib\.urlopen', 'urllib.urlopen', 'high'),
    (r'\brequests\.(get|post|put|delete|patch)\s*\(', 'requests.*', 'medium'),
    (r'\bhttpx\.\w+', 'httpx.*', 'medium'),
    (r'\baiohttp\.\w+', 'aiohttp.*', 'medium'),
    (r'\bftplib\.\w+', 'ftplib.*', 'critical'),

    # Serialization — pickle RCE
    (r'\bpickle\.loads?\s*\(', 'pickle.load()', 'critical'),
    (r'\bpickle\.load\s*\(', 'pickle.load()', 'critical'),
    (r'\bmarshal\.loads?\s*\(', 'marshal.load()', 'critical'),
    (r'\byaml\.load\s*\([^,)]+\)', 'yaml.load() unsafe', 'critical'),
    (r'\bdill\.loads?\s*\(', 'dill.load()', 'critical'),

    # File system
    (r'\bopen\s*\([^,)]*[\'"][wa][\'"]', 'open(write)', 'medium'),
    (r'\bshutil\.rmtree\s*\(', 'shutil.rmtree()', 'high'),
    (r'\bos\.remove\s*\(', 'os.remove()', 'medium'),
    (r'\bos\.rmdir\s*\(', 'os.rmdir()', 'medium'),
    (r'[\'"][/\\\\]etc[/\\\\]', '/etc access', 'high'),
    (r'[\'"][/\\\\]proc[/\\\\]', '/proc access', 'high'),
    (r'\.\./\.\./', 'path traversal', 'high'),

    # Secrets & tokens
    (r'os\.environ\[[\'"]?(AWS_|SECRET_|TOKEN|PASSWORD|API_KEY|DATABASE)',
     'env secret access', 'critical'),
    (r'open\s*\([^)]*\.env', '.env access', 'critical'),
    (r'open\s*\([^)]*secrets', 'secrets access', 'critical'),

    # Importlib dynamic
    (r'\bimportlib\.import_module\s*\(', 'importlib dynamic', 'high'),
    (r'\b__builtins__\[', '__builtins__ access', 'critical'),
    (r'\bglobals\s*\(\s*\)\[', 'globals() access', 'high'),
]


# ============================================================
# MALWARE PATTERNS — JavaScript / CSS
# ============================================================
DANGEROUS_JS_PATTERNS = [
    (r'\beval\s*\(', 'eval()', 'critical'),
    (r'new\s+Function\s*\(', 'new Function()', 'critical'),
    (r'\bsetTimeout\s*\(\s*[\'"]', 'setTimeout(string)', 'high'),
    (r'\bsetInterval\s*\(\s*[\'"]', 'setInterval(string)', 'high'),
    (r'document\.write\s*\(', 'document.write()', 'high'),
    (r'fetch\s*\(\s*[\'"]http', 'fetch external', 'medium'),
    (r'XMLHttpRequest', 'XHR', 'medium'),
    (r'localStorage\.\w+\s*=', 'localStorage write', 'medium'),
    (r'\.innerHTML\s*=', 'innerHTML =', 'medium'),
]


DANGEROUS_CSS_PATTERNS = [
    (r'@import\s+url', '@import url()', 'high'),
    (r'javascript\s*:', 'javascript: URI', 'critical'),
    (r'expression\s*\(', 'expression()', 'critical'),
    (r'behavior\s*:', 'behavior', 'high'),
    (r'url\s*\(\s*[\'"]?data:text/html', 'data:text/html URI', 'critical'),
    (r'url\s*\(\s*[\'"]?http', 'url(http...) external', 'medium'),
    (r'-moz-binding\s*:', '-moz-binding', 'high'),
]


# ============================================================
# SUSPICIOUS FILE EXTENSIONS
# ============================================================
SUSPICIOUS_EXTENSIONS = {
    '.exe': 'critical',
    '.dll': 'critical',
    '.so': 'critical',
    '.dylib': 'critical',
    '.bat': 'critical',
    '.cmd': 'critical',
    '.com': 'critical',
    '.scr': 'critical',
    '.vbs': 'critical',
    '.ps1': 'critical',
    '.jar': 'high',
    '.msi': 'critical',
    '.app': 'critical',
    '.bin': 'medium',
    '.wasm': 'medium',
}


# ============================================================
# SCANNER CLASS
# ============================================================
class SecurityReport:
    def __init__(self):
        self.threats: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
        self.info: Dict[str, Any] = {}
        self.score = 100  # 0-100, càng thấp càng nguy hiểm

    def add_threat(self, severity: str, category: str, message: str, location: str = ''):
        entry = {
            'severity': severity,
            'category': category,
            'message': message,
            'location': location,
            'at': datetime.now(timezone.utc).isoformat(),
        }
        self.threats.append(entry)

        # Trừ điểm
        if severity == 'critical':
            self.score -= 40
        elif severity == 'high':
            self.score -= 20
        elif severity == 'medium':
            self.score -= 8
        else:
            self.score -= 3

        self.score = max(0, self.score)

    def add_warning(self, category: str, message: str, location: str = ''):
        self.warnings.append({
            'category': category,
            'message': message,
            'location': location,
        })
        self.score = max(0, self.score - 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'score': self.score,
            'risk_level': self.risk_level(),
            'is_safe': self.is_safe(),
            'threats': self.threats,
            'warnings': self.warnings,
            'info': self.info,
            'scanned_at': datetime.now(timezone.utc).isoformat(),
        }

    def risk_level(self) -> str:
        if self.score >= 90:
            return 'safe'
        elif self.score >= 70:
            return 'low'
        elif self.score >= 40:
            return 'medium'
        elif self.score >= 15:
            return 'high'
        return 'critical'

    def is_safe(self) -> bool:
        # Chỉ safe khi không có threat critical/high và score >= 70
        for t in self.threats:
            if t['severity'] in ('critical', 'high'):
                return False
        return self.score >= 70


# ============================================================
# SCAN FUNCTIONS
# ============================================================
def scan_text(text: str, filename: str = '') -> SecurityReport:
    """Quét 1 đoạn text (code)"""
    report = SecurityReport()
    report.info['filename'] = filename
    report.info['size_bytes'] = len(text.encode('utf-8'))

    if filename.endswith('.py'):
        patterns = DANGEROUS_PYTHON_PATTERNS
    elif filename.endswith('.js'):
        patterns = DANGEROUS_JS_PATTERNS
    elif filename.endswith('.css'):
        patterns = DANGEROUS_CSS_PATTERNS
    else:
        # Quét cả 3 bộ
        patterns = (
            DANGEROUS_PYTHON_PATTERNS +
            DANGEROUS_JS_PATTERNS +
            DANGEROUS_CSS_PATTERNS
        )

    lines = text.split('\n')
    for line_num, line in enumerate(lines, 1):
        for regex, name, severity in patterns:
            if re.search(regex, line, re.IGNORECASE):
                snippet = line.strip()[:80]
                report.add_threat(
                    severity=severity,
                    category='code_pattern',
                    message=f'Phát hiện pattern nguy hiểm: {name}',
                    location=f'{filename}:{line_num} → {snippet}',
                )

    return report


def scan_css(css: str) -> SecurityReport:
    """Quét CSS cho XSS/injection"""
    report = SecurityReport()
    report.info['type'] = 'css'

    for regex, name, severity in DANGEROUS_CSS_PATTERNS:
        matches = re.finditer(regex, css, re.IGNORECASE)
        for m in matches:
            snippet = css[max(0, m.start() - 20):m.end() + 20]
            report.add_threat(
                severity=severity,
                category='css_pattern',
                message=f'CSS nguy hiểm: {name}',
                location=snippet[:80],
            )

    return report


def scan_cogni_package(file_path: str, max_uncompressed: int = 50 * 1024 * 1024) -> SecurityReport:
    """
    Quét file .cogni (zip-based)
    - Check zip bomb
    - Check file extensions
    - Scan nội dung .py/.js/.css bên trong
    """
    report = SecurityReport()
    report.info['type'] = 'cogni_package'
    report.info['file_size'] = os.path.getsize(file_path)

    if not zipfile.is_zipfile(file_path):
        report.add_threat('high', 'format', 'File .cogni không phải ZIP hợp lệ')
        return report

    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            # Check zip bomb
            total_size = sum(info.file_size for info in z.infolist())
            compressed = os.path.getsize(file_path)
            ratio = total_size / max(compressed, 1)

            report.info['uncompressed_size'] = total_size
            report.info['compression_ratio'] = round(ratio, 2)
            report.info['file_count'] = len(z.infolist())

            if total_size > max_uncompressed:
                report.add_threat(
                    'critical', 'zip_bomb',
                    f'File giải nén quá lớn: {total_size / 1024 / 1024:.1f}MB > 50MB'
                )
                return report

            if ratio > 100:
                report.add_threat(
                    'critical', 'zip_bomb',
                    f'Tỷ lệ nén bất thường: {ratio:.0f}x — có thể là zip bomb'
                )
                return report

            if len(z.infolist()) > 500:
                report.add_threat(
                    'high', 'file_count',
                    f'Quá nhiều file: {len(z.infolist())} > 500'
                )

            # Scan từng file
            has_manifest = False
            for info in z.infolist():
                # Path traversal check
                if '..' in info.filename or info.filename.startswith('/'):
                    report.add_threat(
                        'critical', 'path_traversal',
                        f'Path traversal: {info.filename}'
                    )
                    continue

                # Extension check
                ext = os.path.splitext(info.filename)[1].lower()
                if ext in SUSPICIOUS_EXTENSIONS:
                    report.add_threat(
                        SUSPICIOUS_EXTENSIONS[ext],
                        'suspicious_file',
                        f'File đáng ngờ: {info.filename}'
                    )

                if info.filename == 'manifest.json':
                    has_manifest = True

                # Scan content
                try:
                    if info.file_size > 2 * 1024 * 1024:  # skip file > 2MB
                        continue

                    content = z.read(info.filename).decode('utf-8', errors='ignore')
                    file_report = scan_text(content, info.filename)

                    # Merge
                    for t in file_report.threats:
                        report.add_threat(
                            t['severity'], t['category'],
                            t['message'], t['location']
                        )
                    for w in file_report.warnings:
                        report.add_warning(w['category'], w['message'], w['location'])

                except Exception as e:
                    report.add_warning('read_error', f'Không đọc được {info.filename}: {e}')

            if not has_manifest:
                report.add_warning('manifest', 'Thiếu manifest.json')

    except zipfile.BadZipFile:
        report.add_threat('high', 'format', 'File ZIP bị hỏng')
    except Exception as e:
        report.add_threat('medium', 'scan_error', f'Lỗi scan: {e}')

    return report


def compute_hash(file_path: str) -> str:
    """SHA256 hash của file"""
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


# ============================================================
# QUICK TEST
# ============================================================
if __name__ == '__main__':
    # Test
    bad_code = """
import os
import subprocess
exec("malicious code")
os.system("rm -rf /")
import pickle
pickle.loads(user_input)
"""
    r = scan_text(bad_code, 'evil.py')
    print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))