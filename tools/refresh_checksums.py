"""Refresh checksums only for the reviewed release allowlist; never scan data."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import install


def main():
    if not install.verify_payload(install.load_manifest()):
        raise SystemExit('Payload differs from manifest; review code and installed hashes first')
    names = json.loads((ROOT/'RELEASE_FILES.json').read_text(encoding='utf-8'))
    if not isinstance(names,list) or any(not isinstance(n,str) for n in names) or len(set(names)) != len(names):
        raise SystemExit('Invalid release allowlist')
    lines = []
    for name in sorted(names):
        if name == 'SHA256SUMS.txt':
            continue
        path = install.safe_path(ROOT,name)
        if not path.is_file():
            raise SystemExit('Missing release file: '+name)
        lines.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+name)
    (ROOT/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    print('Updated %d checksums from the release allowlist' % len(lines))


if __name__ == '__main__':
    main()
