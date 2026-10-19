"""CB5: guard identities must agree with the shared conf and real YAML loader."""
from pathlib import Path

from configs.load_model_config import load
from orchestration.laneconf import parse, resolve
from orchestration.laneconf.files import read_text, read_tracks

ROOT = Path(__file__).resolve().parents[2] / 'orchestration'


def test_cb5_lanes_conf_matches_model_config_and_loader():
    tracks = read_tracks(ROOT / 'tracks')
    rows = [row for row in (ROOT / 'lanes.conf').read_text().splitlines()
            if row.strip() and not row.lstrip().startswith('#')]
    assert rows
    assert len({row.split("|", 1)[0] for row in rows}) == len(rows)
    for row in rows:
        name, track, model_conf, hostname, keyvar, model = row.split('|')
        assert track in tracks and (ROOT / 'tracks' / (track + '.sh')).is_file()
        assert name == model_conf + '_' + track
        assert hostname
        conf = resolve(parse(read_text(ROOT / 'models' / (model_conf + '.conf'))), track, tracks)
        assert keyvar == conf['KEYVAR']
        assert model == load(conf['CONFIG'])['model']
