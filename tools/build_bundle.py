"""Build a source-only private bundle with content checksums; no uploads."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).parents[1]
OUT = ROOT / "releases/Story-Writer-0.1.0-private.zip"


def main():
    OUT.parent.mkdir(exist_ok=True)
    entries = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(x in {".git", "__pycache__", "releases"} for x in relative.parts):
            continue
        entries.append(("story-writer/" + str(relative), path.read_bytes()))
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in entries}
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            z.writestr(name, data)
        z.writestr("story-writer/MANIFEST.sha256.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(OUT) as z:
        assert z.testzip() is None
        for name, sha in manifest.items():
            assert hashlib.sha256(z.read(name)).hexdigest() == sha
    print(json.dumps({"path": str(OUT), "files": len(entries) + 1, "bytes": OUT.stat().st_size, "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(), "private": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
