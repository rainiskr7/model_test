"""Characterize the old shell's literal grammar, with deliberate duplicate errors."""
import pytest

from orchestration.laneconf import ConfigError, parse


@pytest.mark.parametrize("text,value", [
    ('K=" a "\n', " a "), ("K=' a '", " a "), ('K="a" \n', '"a" '),
    ('K="\n', '"'), ('K=\'a"\n', '\'a"'), ('K="a"\r\n', '"a"\r'),
    ('K=a\rb\n', 'a\rb'), ('K=\n', ''), ('K=""\n', ''), ("K=''\n", ''),
    ('K=a=b=c\n', 'a=b=c'), ('K= a \n', ' a '), ('K=a #comment\n', 'a #comment'),
    ('K="a" #comment\n', '"a" #comment'), ('K=a', 'a'), ('K=a\\b\n', 'a\\b'),
    ('K=$(touch unexpected); `echo nope`\n', '$(touch unexpected); `echo nope`'),
    ('K=a\vnext\n', 'a\vnext'),
])
def test_literal_values(text, value):
    assert parse(text) == [("K", value)]


def test_blank_comment_and_first_equals():
    assert parse('\n# ignored=x\nK=a=b\n') == [('K', 'a=b')]


@pytest.mark.parametrize("line", [' #comment', ' \t', 'missing'])
def test_only_empty_and_column_zero_comments_are_ignored(line):
    with pytest.raises(ConfigError) as error:
        parse(line)
    assert str(error.value) == 'expected key=value: ' + line


@pytest.mark.parametrize("text,key", [
    ('HOST_DEFAULT=first\nHOST_DEFAULT=second\n', 'HOST_DEFAULT'),
    ('KMMLU_REPS=1\nKMMLU_REPS=2\n', 'KMMLU_REPS'),
    ('REPS=1\nREPS=1\n', 'REPS'),
    ('FULL_REPS=1\nFULL_REPS=2\n', 'FULL_REPS'),
    ('TAUBENCH_STD4_REPS=1\nTAUBENCH_STD4_REPS=2\n', 'TAUBENCH_STD4_REPS'),
], ids=['common', 'scoped', 'identical', 'unselected', 'original_key_spelling'])
def test_duplicate_five_cases(text, key):
    with pytest.raises(ConfigError) as error:
        parse(text)
    assert str(error.value).encode() == ('duplicate key: ' + key).encode()
