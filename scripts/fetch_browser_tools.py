"""Fetch the official, byte-pinned optional axe accessibility test tool."""
import hashlib
import io
import tarfile
import urllib.request
from pathlib import Path

AXE_SHA256 = 'e9e5863c33a874f09bc01acd9234b7e3c871479f5eef8802fa582544465e6d01'


def main():
    data = urllib.request.urlopen('https://registry.npmjs.org/axe-core/-/axe-core-4.11.0.tgz', timeout=30).read()
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        raw = archive.extractfile('package/axe.min.js').read()
        license_text = archive.extractfile('package/LICENSE').read()
    assert hashlib.sha256(raw).hexdigest() == AXE_SHA256
    output = Path('.local')
    output.mkdir(exist_ok=True)
    (output / 'axe.min.js').write_bytes(raw)
    (output / 'axe-LICENSE').write_bytes(license_text)
    print('Verified axe-core 4.11.0', AXE_SHA256)


if __name__ == '__main__':
    main()
