"""무엇: 가벼운 시험 파일 도우미. 입력: 합성 경로/값. 출력: YAML 파일·바이트 스냅샷 (CLI/Arrow 없음)."""

import yaml


def put_yaml(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True))


def output_files(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()}
