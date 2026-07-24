import os, sys, tempfile, pathlib, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

@pytest.fixture()
def db(monkeypatch):
    p = tempfile.mktemp(suffix=".db")
    monkeypatch.setenv("INSTITUTIONAL_DB", p)
    import institutional_db as d
    d.ensure_schema(p)
    yield p
    for ext in ("", "-wal", "-shm"):
        try: os.remove(p+ext)
        except OSError: pass
