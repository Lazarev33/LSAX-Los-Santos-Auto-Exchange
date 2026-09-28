"""Builds LSAX-MASTER-SPEC-v1.0-DRAFT1.zip deterministically (Phase 0 tooling, NOT PRODUCTION CODE).

Contents = every git-tracked file (so build artefacts under bin/obj are never packaged) except release/ and
.gitignore, plus MANIFEST.sha256 (sha256sum format, covers every other packaged file). All entries live under the
folder LSAX-MASTER-SPEC-v1.0-DRAFT1/, sorted, with a fixed timestamp and 0644 permissions, so the same tree always
produces the same ZIP bytes. Refuses to package DLL/PDB/EXE files."""
import hashlib
import os
import subprocess
import sys
import zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
NAME = "LSAX-MASTER-SPEC-v1.0-DRAFT1"
STAMP = (2026, 9, 28, 0, 0, 0)


def main():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    files = sorted(f for f in files if f and not f.startswith("release/") and f not in (".gitignore", "MANIFEST.sha256"))
    bad = [f for f in files if f.lower().endswith((".dll", ".pdb", ".exe"))]
    if bad:
        print("REFUSED: binaries tracked:", bad)
        return 2
    lines = []
    for f in files:
        with open(os.path.join(ROOT, f), "rb") as fh:
            lines.append(f"{hashlib.sha256(fh.read()).hexdigest()}  {f}")
    manifest = "\n".join(lines) + "\n"
    with open(os.path.join(ROOT, "MANIFEST.sha256"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(manifest)
    os.makedirs(os.path.join(ROOT, "release"), exist_ok=True)
    out = os.path.join(ROOT, "release", NAME + ".zip")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in files + ["MANIFEST.sha256"]:
            info = zipfile.ZipInfo(f"{NAME}/{f}", date_time=STAMP)
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(os.path.join(ROOT, f), "rb") as fh:
                z.writestr(info, fh.read())
    digest = hashlib.sha256(open(out, "rb").read()).hexdigest()
    with open(out + ".sha256", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{digest}  {NAME}.zip\n")
    print(f"packaged {len(files)} files + MANIFEST.sha256 -> release/{NAME}.zip")
    print(f"zip sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
