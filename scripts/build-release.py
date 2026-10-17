"""Build reproducible local package archives and checksum release assets.

Requires pip and setuptools already installed. Never fetches build dependencies,
publishes a release, or changes Git tags.
"""
import gzip
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
EPOCH = 1791849600  # 2026-10-13 UTC, fixed release epoch.
VERSION = '1.1.4'


def main():
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    environment = dict(os.environ, SOURCE_DATE_EPOCH=str(EPOCH), PYTHONDONTWRITEBYTECODE='1')
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '.', '--no-build-isolation', '--no-deps', '--no-index', '--wheel-dir', str(output)], cwd=ROOT, env=environment, check=True)
    subprocess.run([sys.executable, '-c', 'from setuptools.build_meta import build_sdist; build_sdist("dist")'], cwd=ROOT, env=environment, check=True)
    source = output / f'champollion_protocol-{VERSION}.tar.gz'
    buffer = io.BytesIO()
    with tarfile.open(source, 'r:gz') as original, tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as normalized:
        for member in sorted(original.getmembers(), key=lambda m: m.name):
            if not member.isfile() and not member.isdir():
                raise ValueError(f'unsupported source archive member: {member.name}')
            member.uid = member.gid = 0
            member.uname = member.gname = ''
            member.mtime = EPOCH
            member.mode = 0o755 if member.isdir() else 0o644
            member.pax_headers = {}
            normalized.addfile(member, original.extractfile(member) if member.isfile() else None)
    with source.open('wb') as handle, gzip.GzipFile(filename='', fileobj=handle, mode='wb', mtime=EPOCH) as compressed:
        compressed.write(buffer.getvalue())
    archives = [output / f'champollion_protocol-{VERSION}-py3-none-any.whl', source]
    sums = ''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in archives)
    (output / 'SHA256SUMS').write_text(sums, encoding='utf-8')
    print(sums, end='')
    print(f'After verification: git tag -a v{VERSION} -m "Champollion {VERSION}"')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Champollion release build failed: {error}', file=sys.stderr)
        sys.exit(1)
