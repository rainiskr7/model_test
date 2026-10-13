"""stdout report; the final line is the preregistered primary variant."""


def print_report(report):
    for name, result in report["rules"].items():
        print(f"{name} {result['status']} {result['numerator']}/{result['denominator']}")
        if name in ("R2v3", "R4"):
            for variant, row in result["variants"].items():
                print(f"{name}.{variant} {row['status']} {row['numerator']}/{row['denominator']}")
    print("LENGTH variant tokenizer method p50 p95 max >8192/requests")
    for variant, result in report["rules"]["R2v3"]["variants"].items():
        for tokenizer, methods in result["measurements"].items():
            for method, row in methods.items():
                print(f"{variant} {tokenizer} {method} {row['p50']:.2f} {row['p95']:.2f} {row['max']} {row['numerator']}/{row['denominator']}")
    copy = report["statistics"]["copy_baseline"]
    changed, prior = copy["changed_including_first"], copy["changed_with_previous"]
    print(f"COPY {copy['numerator']}/{copy['denominator']} first_USER={copy['first_user_count']}")
    print(f"CHANGED including_first={changed['numerator']}/{changed['denominator']} with_previous={prior['numerator']}/{prior['denominator']}")
    distribution = report["statistics"]["distribution"]
    second = distribution["second_slot_none"]
    print(f"DISTRIBUTION active={distribution['active_intent_counts']} frames={distribution['frame_counts']} second_NONE={second['numerator']}/{second['denominator']}")
    missing = copy["frame_missing"]
    print(f"FRAME_MISSING {missing['numerator']}/{missing['denominator']}")
    timing = report["rules"]["R6"]
    previous, following = timing["previous_user"], timing["next_user"]
    print(f"R6_NEIGHBORS previous={previous['numerator']}/{previous['denominator']} next={following['numerator']}/{following['denominator']}")
    version = report["statistics"]["version_diff"]
    full, actions = version["success_any_mismatch"]["full"], version["success_any_mismatch"]["actions_only"]
    print(f"VERSION mapping_valid={version['mapping_valid']} full={full['numerator']}/{full['denominator']}({full['status']}) actions_only={actions['numerator']}/{actions['denominator']}({actions['status']})")
    injections = report["rules"]["R7"]["injection_tests"]
    print(f"R7_INJECTIONS {sum(t['detected'] for t in injections['tests'])}/6 baseline={injections['baseline_passed']}")
    print(f"SPEC_AMBIGUOUS {len(report['spec_ambiguities'])} triggered={sum(a['triggered'] for a in report['spec_ambiguities'])}")
    if report["primary_variant"] == "STOP":
        print("NOTICE: 행동판 R2v3 또는 R4 FAIL — 모델 평가를 멈추고 사용자에게 알립니다.")
    if report["primary_variant"] is None:
        print("SPEC-AMBIGUOUS: 주 지표 선택이 정의되지 않았습니다. result.json을 확인하세요.")
    else:
        print(f"PRIMARY_VARIANT: {report['primary_variant']}")
