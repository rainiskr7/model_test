"""Read English SGD; absent corresponding IDs are handled by version_diff."""

from common.io import required_files
from config import ENGLISH_DIR
from load.kosgd import read_dialogues


def load():
    paths = required_files(ENGLISH_DIR, "dialogues_*.json")
    return read_dialogues(paths), paths
