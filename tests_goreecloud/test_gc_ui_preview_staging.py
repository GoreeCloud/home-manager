"""Offline negative tests for staging exactly four verified GC UI source assets."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import stage_gc_ui_home_manager_preview as stage  # noqa: E402

LICENSE=b"Apache License\nVersion 2.0, January 2004\n"
ASSETS={
    "src/index.mjs": b"export const GC_UI_VERSION='1.0.1';\n",
    "src/gc-color-engine.mjs": b"export function generateTheme(){return {}}\n",
    "src/gc-theme-runtime.mjs": b"export function createThemeController(){return {}}\n",
    "styles/gc.v1.generated.css": b":root{--gc-v1-color-canvas:#fff}\n",
}
MANIFEST={
  "name":"@goreecloud/gc-ui",
  "version":"1.0.1",
  "license":"Apache-2.0",
  "private":False,
  "dependencies":{},
  "exports":{".":{"import":"./src/index.mjs"},"./tokens":"./tokens/gc.v1.tokens.json","./css/tokens":"./styles/gc.v1.generated.css"}
}


def fixture(*, modify_provenance:bool=False,extra:tuple[str,bytes]|None=None)->bytes:
    entries={
      "package/package.json":json.dumps(MANIFEST).encode(),
      "package/LICENSE":LICENSE,
      "package/tokens/gc.v1.tokens.json":b'{"gc":"tokens"}\n',
      **{"package/"+key:body for key,body in ASSETS.items()}
    }
    provenance={
      "sourceRepository":"GoreeCloud/gc-ui",
      "releaseVersion":"1.0.1",
      "files":{key:sha256(body).hexdigest() for key,body in ASSETS.items()}
    }
    if modify_provenance:
      provenance["files"]["src/index.mjs"]="0"*64
    entries["package/provenance.json"]=json.dumps(provenance).encode()
    if extra:
      entries[extra[0]]=extra[1]
    buf=BytesIO()
    with tarfile.open(fileobj=buf,mode="w:gz") as archive:
      for name,body in entries.items():
        info=tarfile.TarInfo(name)
        info.size=len(body)
        archive.addfile(info,BytesIO(body))
    return buf.getvalue()


class GCUIStageTests(unittest.TestCase):
    def setUp(self)->None:
      temp=tempfile.TemporaryDirectory()
      self.addCleanup(temp.cleanup)
      self.root=Path(temp.name)
      self.destination=self.root/"gc-ui"

    def test_only_allowlisted_verified_assets_staged(self)->None:
      result=stage.stage_foundations(fixture(),self.destination,verify_sha=False)
      self.assertEqual(result["source_files_staged"],4)
      self.assertTrue(result["source_manifest_checks_passed"])
      self.assertFalse(result["frontend_runtime_built"])
      self.assertFalse(result["production_frontend_modified"])
      found={p.relative_to(self.destination).as_posix() for p in self.destination.rglob("*") if p.is_file()}
      self.assertEqual(found,set(stage.FILES.values()))
      for source,relative in stage.FILES.items():
        self.assertEqual((self.destination/relative).read_bytes(),ASSETS[source.removeprefix("package/")])

    def test_unverified_official_hash_stops_all_staging(self)->None:
      with self.assertRaisesRegex(ValueError,"SHA-256"):
        stage.stage_foundations(fixture(),self.destination)
      self.assertFalse(self.destination.exists())

    def test_modified_source_identity_is_rejected(self)->None:
      with self.assertRaisesRegex(ValueError,"digest mismatch"):
        stage.stage_foundations(fixture(modify_provenance=True),self.destination,verify_sha=False)
      self.assertFalse(self.destination.exists())

    def test_unknown_source_archive_members_are_not_staged(self)->None:
      result=stage.stage_foundations(fixture(extra=("package/experimental/unreviewed.js",b"console.log('do not execute')")),self.destination,verify_sha=False)
      self.assertEqual(result["source_files_staged"],4)
      self.assertFalse((self.destination/"experimental").exists())

    def test_existing_destination_preserved(self)->None:
      self.destination.mkdir()
      (self.destination/"keep.txt").write_text("preserve")
      with self.assertRaisesRegex(ValueError,"must be new"):
        stage.stage_foundations(fixture(),self.destination,verify_sha=False)
      self.assertEqual((self.destination/"keep.txt").read_text(),"preserve")

    def test_source_tar_traversal_rejected_before_staging(self)->None:
      with self.assertRaisesRegex(ValueError,"unsafe"):
        stage.stage_foundations(fixture(extra=("package/../../bad.js",b"unsafe")),self.destination,verify_sha=False)
      self.assertFalse(self.destination.exists())


if __name__=="__main__":
    unittest.main()
