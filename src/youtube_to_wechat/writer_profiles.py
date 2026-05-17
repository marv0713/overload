from dataclasses import dataclass
from pathlib import Path


@dataclass
class LoadedWriterProfile:
    name: str
    prompt: str
    path: Path


def load_writer_profile(name: str, profiles_dir: Path = Path("config/writer_profiles")) -> LoadedWriterProfile:
    path = profiles_dir / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Writer profile not found: {path}")
    return LoadedWriterProfile(
        name=name,
        prompt=path.read_text(encoding="utf-8").strip(),
        path=path,
    )
