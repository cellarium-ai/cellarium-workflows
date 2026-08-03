"""
Tests for prepare_config_with_overrides in shared_components.

The local extract_*.h5ad files in the repo root (10 files, 10 000 obs each)
are used as fixtures.  gcsfs is patched so no real GCS calls are made; the
mock maps expected GCS paths straight back to the local file paths.
"""

import os
import re
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from ruamel.yaml import YAML

from cellarium.workflows.shared_components import prepare_config_with_overrides

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
EXTRACT_FILES = sorted(
    REPO_ROOT.glob("extract_*.h5ad"),
    key=lambda p: int(re.search(r"extract_(\d+)", p.name).group(1)),
)
N_FILES = len(EXTRACT_FILES)  # 10
OBS_PER_FILE = 10_000  # confirmed from local files
FAKE_BUCKET = "gs://fake-bucket/fake-prefix"


def _make_fake_fs():
    """
    Return a mock that mimics the gcsfs.GCSFileSystem API used by
    prepare_config_with_overrides:
      - .glob(pattern)  -> list of GCS-style paths
      - .open(path, mode) -> file-like object backed by the local h5ad
    """
    fake_fs = MagicMock()

    # glob: return one fake GCS path per local extract file
    fake_gcs_paths = [
        f"fake-bucket/fake-prefix/extract_{i}.h5ad" for i in range(N_FILES)
    ]
    fake_fs.glob.return_value = fake_gcs_paths

    def _open(gcs_path, mode="rb"):
        # Map e.g. "fake-bucket/fake-prefix/extract_3.h5ad" -> local file
        filename = gcs_path.split("/")[-1]
        local_path = REPO_ROOT / filename
        return open(local_path, "rb")

    fake_fs.open.side_effect = _open
    return fake_fs


def _load_yaml(path: str) -> dict:
    yaml = YAML()
    with open(path) as f:
        return yaml.load(f)


def _base_config_yaml() -> str:
    return textwrap.dedent("""\
        data:
          dadc:
            class_path: cellarium.ml.data.DistributedAnnDataCollection
            init_args:
              filenames: gs://old-bucket/old-prefix/extract_{0..4}.h5ad
              shard_size: 500
              last_shard_size: 123
              max_cache_size: 2
        """)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoExtractBucket:
    """When extract_bucket is None the original path is returned unchanged."""

    def test_returns_original_path(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(_base_config_yaml())
        result = prepare_config_with_overrides(str(cfg), extract_bucket=None)
        assert result == str(cfg)

    def test_file_is_not_modified(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        original = _base_config_yaml()
        cfg.write_text(original)
        prepare_config_with_overrides(str(cfg), extract_bucket=None)
        assert cfg.read_text() == original


class TestExtractBucketPatching:
    """With extract_bucket supplied, filenames / shard_size / last_shard_size
    are updated to match the discovered shards."""

    def test_filenames_pattern(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(_base_config_yaml())
        fake_fs = _make_fake_fs()
        with patch(
            "cellarium.workflows.shared_components.gcsfs.GCSFileSystem",
            return_value=fake_fs,
        ):
            out = prepare_config_with_overrides(str(cfg), FAKE_BUCKET)
        doc = _load_yaml(out)
        filenames = doc["data"]["dadc"]["init_args"]["filenames"]
        assert filenames == f"{FAKE_BUCKET}/extract_{{0..{N_FILES - 1}}}.h5ad"

    def test_shard_size_from_first_file(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(_base_config_yaml())
        fake_fs = _make_fake_fs()
        with patch(
            "cellarium.workflows.shared_components.gcsfs.GCSFileSystem",
            return_value=fake_fs,
        ):
            out = prepare_config_with_overrides(str(cfg), FAKE_BUCKET)
        doc = _load_yaml(out)
        assert doc["data"]["dadc"]["init_args"]["shard_size"] == OBS_PER_FILE

    def test_last_shard_size_from_last_file(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(_base_config_yaml())
        fake_fs = _make_fake_fs()
        with patch(
            "cellarium.workflows.shared_components.gcsfs.GCSFileSystem",
            return_value=fake_fs,
        ):
            out = prepare_config_with_overrides(str(cfg), FAKE_BUCKET)
        doc = _load_yaml(out)
        assert doc["data"]["dadc"]["init_args"]["last_shard_size"] == OBS_PER_FILE

    def test_returns_different_path_from_input(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(_base_config_yaml())
        fake_fs = _make_fake_fs()
        with patch(
            "cellarium.workflows.shared_components.gcsfs.GCSFileSystem",
            return_value=fake_fs,
        ):
            out = prepare_config_with_overrides(str(cfg), FAKE_BUCKET)
        assert out != str(cfg)

    def test_original_config_file_unchanged(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        original = _base_config_yaml()
        cfg.write_text(original)
        fake_fs = _make_fake_fs()
        with patch(
            "cellarium.workflows.shared_components.gcsfs.GCSFileSystem",
            return_value=fake_fs,
        ):
            prepare_config_with_overrides(str(cfg), FAKE_BUCKET)
        assert cfg.read_text() == original

    def test_output_is_valid_yaml_file(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(_base_config_yaml())
        fake_fs = _make_fake_fs()
        with patch(
            "cellarium.workflows.shared_components.gcsfs.GCSFileSystem",
            return_value=fake_fs,
        ):
            out = prepare_config_with_overrides(str(cfg), FAKE_BUCKET)
        assert os.path.isfile(out)
        doc = _load_yaml(out)
        assert "data" in doc

    def test_trailing_slash_on_bucket_stripped(self, tmp_path):
        """A trailing slash on the bucket prefix should not produce double slashes."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(_base_config_yaml())
        fake_fs = _make_fake_fs()
        with patch(
            "cellarium.workflows.shared_components.gcsfs.GCSFileSystem",
            return_value=fake_fs,
        ):
            out = prepare_config_with_overrides(str(cfg), FAKE_BUCKET + "/")
        doc = _load_yaml(out)
        filenames = doc["data"]["dadc"]["init_args"]["filenames"]
        assert "//" not in filenames.replace("gs://", "")


class TestErrorCases:
    def test_no_matching_files_raises(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(_base_config_yaml())
        fake_fs = MagicMock()
        fake_fs.glob.return_value = []
        with patch(
            "cellarium.workflows.shared_components.gcsfs.GCSFileSystem",
            return_value=fake_fs,
        ):
            with pytest.raises(
                FileNotFoundError, match="No extract_.*\\.h5ad files found"
            ):
                prepare_config_with_overrides(str(cfg), FAKE_BUCKET)

    def test_missing_dadc_key_raises(self, tmp_path):
        bad_yaml = textwrap.dedent("""\
            data:
              something_else:
                init_args: {}
            """)
        cfg = tmp_path / "config.yaml"
        cfg.write_text(bad_yaml)
        fake_fs = _make_fake_fs()
        with patch(
            "cellarium.workflows.shared_components.gcsfs.GCSFileSystem",
            return_value=fake_fs,
        ):
            with pytest.raises(KeyError):
                prepare_config_with_overrides(str(cfg), FAKE_BUCKET)
