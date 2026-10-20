"""Delete only the temporary BASE explicitly owned by the current invocation."""
from pathlib import Path
import shutil

from orchestration.smoke.isolation import outside


def remove_base(base, root, *, created):
    """Validate ownership and the canonical temp parent before removing one tree."""
    base, created = Path(base), Path(created)
    if base != created:
        raise ValueError('cleanup target is not the BASE created by this invocation')
    if base.parent != Path('/tmp').resolve() or not base.name.startswith('serving-smoke-'):
        raise ValueError('cleanup target is not a canonical smoke temporary directory')
    if base.name == 'serving-smoke-' or base.is_symlink() or not base.is_dir():
        raise ValueError('cleanup target must be a real, uniquely named directory')
    outside(base, root)
    # rmtree unlinks internal symlinks; never resolve the data/config/venv children.
    shutil.rmtree(base)


def finish(summary, root, base, keep=False):
    """Record successful deletion, retaining the serving verdict on cleanup errors."""
    summary['base_kept'] = base is not None
    if base is not None and not keep and summary['rc'] in (0, 2):
        try:
            remove_base(base, root, created=base)
        except (OSError, ValueError) as exc:
            summary['cleanup_error'] = str(exc)
        else:
            summary['base_kept'] = False
    return summary
