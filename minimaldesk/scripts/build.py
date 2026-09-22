"""Build on the target OS: Windows -> EXE directory, Linux -> executable directory."""
from pathlib import Path
import importlib.util
import subprocess
import sys


def main() -> int:
    if sys.platform not in {'win32', 'linux'}:
        print('Build on Windows or Linux.', file=sys.stderr)
        return 1
    if importlib.util.find_spec('PyInstaller') is None:
        print('Install build tools: python -m pip install -r requirements-dev.txt', file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parents[1]
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
            '--onedir', '--name', 'MinimalDesk', '--paths', str(root/'client'),
            '--distpath', str(root/'dist'), '--workpath', str(root/'build'), str(root/'launch.py')]
    try:
        subprocess.run(args, cwd=root, check=True)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    print('Build created in dist/MinimalDesk. Distribute the ENTIRE directory, not only the executable.')
    print('This is an unsigned build. Test it on a separate target machine before distributing it.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
