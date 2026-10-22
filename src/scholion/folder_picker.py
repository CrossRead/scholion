"""Native local folder selection; manual entry remains available on every host."""
from __future__ import annotations

import base64
import json
import ntpath
import os
import subprocess
import sys

from .i18n import t


def _windows_command(prompt: str) -> list[str]:
    # The prompt is data inside an encoded script, never PowerShell source.
    prompt64 = base64.b64encode(prompt.encode('utf-8')).decode('ascii')
    script = r'''
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Windows.Forms
if (-not [Environment]::UserInteractive) { throw 'No interactive desktop session' }
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$dialog.Description = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__PROMPT__'))
try {
    $result = $dialog.ShowDialog($owner)
    if ($result -eq [System.Windows.Forms.DialogResult]::OK) {
        @{ok=$true;path=$dialog.SelectedPath} | ConvertTo-Json -Compress
    } else {
        @{ok=$false;canceled=$true} | ConvertTo-Json -Compress
    }
} finally {
    $dialog.Dispose()
    $owner.Dispose()
}
'''.replace('__PROMPT__', prompt64)
    # Use the system executable, never a powershell.exe in the server's cwd.
    executable = ntpath.join(os.environ.get('SystemRoot', r'C:\Windows'),
                             'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    return [executable, '-NoProfile', '-NonInteractive', '-STA', '-EncodedCommand',
            base64.b64encode(script.encode('utf-16le')).decode('ascii')]


def choose(prompt: str) -> dict:
    if sys.platform not in ('darwin', 'win32'):
        return {'ok': False, 'reason': 'native_unavailable', 'manual_available': True,
                'error': t('folder.native_unavailable')}
    if sys.platform == 'win32':
        command = _windows_command(prompt)
    else:
        safe = prompt.replace('"', "'")
        script = ('tell application "System Events" to activate\n'
                  f'set theFolder to choose folder with prompt "{safe}"\n'
                  'return POSIX path of theFolder')
        command = ['osascript', '-e', script]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=300)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'reason': 'dialog_timeout', 'manual_available': True,
                'error': t('folder.dialog_timeout')}
    except OSError as exc:
        return {'ok': False, 'reason': 'dialog_unavailable', 'manual_available': True,
                'error': t('server.pick.failed'), 'detail': type(exc).__name__}
    if result.returncode != 0:
        error = result.stderr or ''
        if sys.platform == 'darwin' and ('-128' in error or 'User canceled' in error or 'отмен' in error.lower()):
            return {'ok': False, 'canceled': True, 'manual_available': True}
        return {'ok': False, 'reason': 'dialog_failed', 'manual_available': True,
                'error': (error.strip() or t('server.pick.failed')) if sys.platform == 'darwin' else t('server.pick.failed'),
                'detail': error.strip()}
    if sys.platform == 'win32':
        try:
            selected = json.loads(result.stdout.lstrip('\ufeff').strip())
            if isinstance(selected, dict) and selected.get('canceled') is True:
                return {'ok': False, 'canceled': True, 'manual_available': True}
            path = selected.get('path') if isinstance(selected, dict) and selected.get('ok') is True else None
        except (ValueError, AttributeError):
            path = None
    else:
        path = result.stdout.strip()
    if not isinstance(path, str) or not path.strip():
        return {'ok': False, 'reason': 'empty_path', 'manual_available': True,
                'error': t('server.pick.empty_path')}
    return {'ok': True, 'path': path, 'manual_available': True}


def probe(path: str) -> dict:
    """Bound filesystem probing (including unavailable UNC shares) before writing.

    The disposable child imports only the standard library, receives the path as
    an argument and never reads a profile or writes configuration.
    """
    script = """import json,sys
from pathlib import Path
try:
    p=Path(sys.argv[1]).expanduser()
    ok=p.is_dir()
    if ok: next(p.iterdir(),None)
    print(json.dumps({'ok':ok,'reason':None if ok else 'folder_not_found'}))
except (OSError,ValueError):
    print(json.dumps({'ok':False,'reason':'folder_unavailable'}))
"""
    try:
        result = subprocess.run([sys.executable, '-c', script, path], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=8)
        response = json.loads(result.stdout)
        if result.returncode == 0 and isinstance(response, dict) and response.get('ok') is True:
            return {'ok': True}
        reason = response.get('reason') if isinstance(response, dict) else 'folder_unavailable'
    except subprocess.TimeoutExpired:
        return {'ok': False, 'reason': 'path_timeout', 'error': t('folder.path_timeout')}
    except (OSError, ValueError):
        reason = 'folder_unavailable'
    return {'ok': False, 'reason': reason,
            'error': t('store.folder_not_found', path=path) if reason == 'folder_not_found' else t('folder.access_failed')}
