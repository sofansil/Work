import re

def is_valid_email(email: str) -> bool:
    """
    간단하면서도 실무에서 충분히 쓸 수 있는 이메일 검증 정규식.
    - 로컬 파트가 점(.)으로 시작하거나 끝나면 안 됨
    - 연속된 점(..) 금지
    - 도메인 레이블은 하이픈(-)로 시작하면 안 됨
    - 최종 TLD는 최소 2자
    """
    pattern = re.compile(
        r"^(?!\.)"                                 # 로컬 파트가 .로 시작하면 안 됨
        r"(?!.*\.\.)"                              # 연속된 점 금지
        r"[A-Za-z0-9._%+-]+(?<!\.)"                # 로컬 파트 (끝이 .이면 안 됨)
        r"@"                                       # @
        r"(?:(?!-)[A-Za-z0-9-]+(?:\.(?!-)[A-Za-z0-9-]+)*)"  # 도메인 레이블(하이픈 시작 금지)
        r"\.[A-Za-z]{2,}$",                        # 최종 TLD
        re.IGNORECASE
    )
    return bool(pattern.match(email))


samples = [
    "user@example.com",                        # valid
    "user.name+tag+sorting@example.co.uk",     # valid
    "user_name@example-domain.com",            # valid
    "user@sub.example.com",                    # valid
    ".user@example.com",                       # invalid (로컬 파트가 .로 시작)
    "user.@example.com",                       # invalid (로컬 파트가 .로 끝남)
    "user..dots@example.com",                  # invalid (연속된 점)
    "user@-example.com",                       # invalid (도메인 레이블이 -로 시작)
    "user@example",                            # invalid (TLD 없음)
    "very.common@example.com"                  # valid
]

for s in samples:
    print(f"{s:35} -> {'VALID' if is_valid_email(s) else 'INVALID'}")

