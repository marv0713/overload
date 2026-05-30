from dataclasses import dataclass
from pathlib import Path


@dataclass
class LoadedWriterProfile:
    name: str
    prompt: str
    path: Path


import os

def load_writer_profile(name: str, profiles_dir: Path = Path("config/writer_profiles")) -> LoadedWriterProfile:
    db_url = os.environ.get("SUPABASE_DB_URL")
    if db_url:
        try:
            import psycopg2
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT value FROM overlord_config WHERE key = 'writer_profiles';")
                    row = cur.fetchone()
                    if row and row[0] and name in row[0]:
                        return LoadedWriterProfile(
                            name=name,
                            prompt=row[0][name].strip(),
                            path=Path(f"supabase_{name}"),
                        )
        except Exception as e:
            print(f"Warning: Failed to load profile from Supabase, falling back to local: {e}")

    path = profiles_dir / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Writer profile not found: {path}")
    return LoadedWriterProfile(
        name=name,
        prompt=path.read_text(encoding="utf-8").strip(),
        path=path,
    )
