"""File reads must retain CR and use the caller-provided track directory."""
import pytest

from orchestration.laneconf import ConfigError
from orchestration.laneconf.files import read_text, read_tracks


def test_read_preserves_cr_and_missing_path_message(tmp_path):
    path = tmp_path / 'model.conf'
    path.write_bytes(b'K="a"\r\nK2=b\rc')
    assert read_text(path) == 'K="a"\r\nK2=b\rc'
    path.unlink()
    with pytest.raises(ConfigError) as error:
        read_text(path)
    assert str(error.value) == 'missing conf: ' + str(path)


def test_track_list_is_explicit_and_only_files(tmp_path):
    (tmp_path / 'kmmlu.sh').touch()
    (tmp_path / 'full.sh').symlink_to('kmmlu.sh')
    (tmp_path / 'bad-name.sh').touch()
    (tmp_path / 'UPPER.sh').touch()
    (tmp_path / 'directory.sh').mkdir()
    assert read_tracks(tmp_path) == ('full', 'kmmlu')
    assert read_tracks(tmp_path / 'directory.sh') == ()
