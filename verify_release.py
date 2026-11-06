"""Check this kit and its installer without importing PyAEDT or contacting AEDT."""
from pathlib import Path
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import install


def main():
    sums = ROOT/'SHA256SUMS.txt'
    if not sums.is_file():
        print('Missing SHA256SUMS.txt')
        return 1
    seen = set()
    for line in sums.read_text(encoding='utf-8').splitlines():
        digest,name = line.split('  ',1)
        path = install.safe_path(ROOT,name)
        if name in seen or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            print('Checksum failure: '+name)
            return 1
        seen.add(name)
    if not install.verify_payload(install.load_manifest()):
        return 1
    suite = unittest.defaultTestLoader.discover(str(ROOT/'files/tests'),pattern='test_kit*.py')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print('Checksums are integrity checks, not publisher authentication.')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
