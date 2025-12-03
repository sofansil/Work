import shutil
from pathlib import Path

# 상수는 대문자로 코딩: 정해진 값을 미리 셋팅
SOURCE = Path(r"C:\Users\sofan\Downloads")

# 확장자별 대상 폴더 (소문자 기준)
EXT_TO_FOLDER = {
    "jpg": "images",
    "jpeg": "images",
    "csv": "data",
    "xlsx": "data",
    "txt": "docs",
    "doc": "docs",
    "docx": "docs",
    "pdf": "docs",
    "zip": "archive",
}

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def unique_destination(dest: Path) -> Path:
    if not dest.exists():
        return dest
    stem, suf = dest.stem, dest.suffix
    counter = 1
    while True:
        candidate = dest.with_name(f"{stem}_{counter}{suf}")
        if not candidate.exists():
            return candidate
        counter += 1

def organize():
    if not SOURCE.exists() or not SOURCE.is_dir():
        print(f"원본 폴더가 없습니다: {SOURCE}")
        return

    counts = {}
    for item in SOURCE.iterdir():
        if not item.is_file():
            continue
        ext = item.suffix.lower().lstrip(".")
        target_folder_name = EXT_TO_FOLDER.get(ext)
        if not target_folder_name:
            continue
        target_dir = SOURCE / target_folder_name
        ensure_dir(target_dir)
        dest = target_dir / item.name
        dest = unique_destination(dest)
        try:
            shutil.move(str(item), str(dest))
            counts[target_folder_name] = counts.get(target_folder_name, 0) + 1
            print(f"이동: {item.name} -> {target_dir.name}\\{dest.name}")
        except Exception as e:
            print(f"실패: {item.name} ({e})")

    if counts:
        print("요약:")
        for k, v in counts.items():
            print(f"  {k}: {v}개 이동")
    else:
        print("이동할 파일이 없습니다.")

if __name__ == "__main__":
    organize()

