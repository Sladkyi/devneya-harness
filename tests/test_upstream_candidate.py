import hashlib
import io
from pathlib import Path
import sys
import tarfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import upstream_candidate as candidate


class UpstreamCandidateTests(unittest.TestCase):
    def test_downgrade_only_release_does_not_trigger_a_build(self):
        pinned = {"dsh": "0.2.2-rc.10", "tui": "0.20.2"}
        with patch.object(candidate, "npm_manifest", side_effect=[
            {"version": "0.2.2-rc.9"}, {"version": "0.20.2"},
        ]), patch.dict(candidate.os.environ, {}, clear=True):
            self.assertEqual(candidate.output_versions(pinned, False), {**pinned, "build": "false"})

    def test_a_newer_version_of_either_component_triggers_a_build(self):
        pinned = {"dsh": "0.2.2-rc.10", "tui": "0.20.2"}
        with patch.object(candidate, "npm_manifest", side_effect=[
            {"version": "0.2.2"}, {"version": "0.20.2"},
        ]), patch.dict(candidate.os.environ, {}, clear=True):
            self.assertEqual(candidate.output_versions(pinned, False), {
                "dsh": "0.2.2", "tui": "0.20.2", "build": "true",
            })

    def test_only_identical_patch_preimages_are_rebound(self):
        package = "@deepseek-harness-tui/dsh-tui"
        manifest = {package: {"version": "0.20.3"}}
        row = {
            "package": package, "path": "lib/file.js", "version": "0.20.2",
            "sha256": hashlib.sha256(b"original").hexdigest(),
        }
        for data, accepted in ((b"original", True), (b"changed", False)):
            with self.subTest(accepted=accepted):
                archive = io.BytesIO()
                member = tarfile.TarInfo("package/lib/file.js")
                member.size = len(data)
                with tarfile.open(fileobj=archive, mode="w:gz") as handle:
                    handle.addfile(member, io.BytesIO(data))
                archive.seek(0)
                tested = row.copy()
                with patch.object(candidate, "package_archive", return_value=tarfile.open(fileobj=archive)):
                    if accepted:
                        candidate.check_patch_sources([tested], manifest)
                        self.assertEqual(tested["version"], "0.20.3")
                    else:
                        with self.assertRaisesRegex(ValueError, "lib/file.js changed"):
                            candidate.check_patch_sources([tested], manifest)
                        self.assertEqual(tested["version"], row["version"])
