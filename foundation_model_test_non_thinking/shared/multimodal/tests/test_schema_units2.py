"""R4 contracts captured by executing original blocks on synthetic inputs."""
import shared.multimodal.publish.schema as subject


def test_model_identity_absent():
    actual = subject._validate_model_identity({})
    assert actual == None


def test_model_identity_mismatch():
    try:
        subject._validate_model_identity({'model': 'a', 'model_identity': {'canonical_id': 'a', 'serving_name': 'b', 'mapped': True}})
    except ValueError as exc:
        actual = (type(exc).__name__, str(exc))
    assert actual == ('ValueError', 'model_identity.serving_name must preserve model')


def test_accuracy_axis_fraction():
    actual = subject._validate_accuracy_axis({'benchmark_id': 'K-DTCBench', 'metrics': {'axes': [{'name': 'overall', 'unit': 'fraction', 'numerator': 1, 'denominator': 3, 'value': 1/3}]}}, subject.PublishStatus.NATIVE)
    assert actual == None


def test_accuracy_axis_bool_rejected():
    try:
        subject._validate_accuracy_axis({'benchmark_id': 'K-DTCBench', 'metrics': {'axes': [{'name': 'overall', 'unit': 'fraction', 'numerator': True, 'denominator': 1, 'value': 1.0}]}}, subject.PublishStatus.NATIVE)
    except ValueError as exc:
        actual = (type(exc).__name__, str(exc))
    assert actual == ('ValueError', 'invalid publishable overall fraction axis')


def test_counts_valid():
    actual = subject._validate_counts({'counts': {'attempted': 2, 'measured': 2, 'errored': 0, 'unresolved': 0, 'correct_measured': 1}}, subject.PublishStatus.NATIVE)
    assert actual == None


def test_counts_completion_invariant():
    try:
        subject._validate_counts({'counts': {'attempted': 2, 'measured': 1, 'errored': 0, 'unresolved': 0, 'correct_measured': 1}}, subject.PublishStatus.NATIVE)
    except ValueError as exc:
        actual = (type(exc).__name__, str(exc))
    assert actual == ('ValueError', 'attempted count invariant failed')
