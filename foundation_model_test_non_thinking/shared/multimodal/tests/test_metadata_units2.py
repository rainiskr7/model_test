"""R4 contracts captured by executing original blocks on synthetic inputs."""
from pathlib import Path
from unittest.mock import patch
import shared.multimodal.benches.metadata as subject


def test_provenance_explicit():
    with patch.object(subject, 'get_hf_dataset_revision', side_effect=AssertionError), patch.object(subject, 'get_git_commit', side_effect=AssertionError), patch.object(subject, 'get_eval_script_hash', side_effect=AssertionError):
        actual = subject._resolve_provenance('ds', 'revision', 'explicit', Path('/synthetic/repo'), 'commit', 'eval.py', 'hash')
    assert actual == ('revision', 'explicit', 'commit', 'hash')


def test_provenance_lookup():
    with patch.object(subject, 'get_hf_dataset_revision', return_value='rev') as dataset, patch.object(subject, 'get_git_commit', return_value='sha') as repo, patch.object(subject, 'get_eval_script_hash', return_value='hash') as script:
        actual = subject._resolve_provenance('ds', None, None, Path('/synthetic/repo'), None, 'eval.py', None)
        actual = (actual, dataset.call_args.args, str(repo.call_args.args[0]), script.call_args.args)
    assert actual == (('rev', 'latest_captured', 'sha', 'hash'), ('ds',), '/synthetic/repo', ('eval.py',))


def test_environment_capture_order():
    with patch.object(subject.sys, 'version', '3.test synthetic'), patch.object(subject.platform, 'platform', return_value='synthetic'), patch.object(subject, 'get_package_version', side_effect=lambda name: name + '-version') as versions:
        actual = (list(subject._capture_environment().items()), [call.args for call in versions.call_args_list])
    assert actual == ([('python', '3.test'),
      ('platform', 'synthetic'),
      ('openai_pkg', 'openai-version'),
      ('datasets_pkg', 'datasets-version'),
      ('pillow_pkg', 'pillow-version'),
      ('huggingface_hub_pkg', 'huggingface_hub-version')],
     [('openai',), ('datasets',), ('pillow',), ('huggingface_hub',)])
