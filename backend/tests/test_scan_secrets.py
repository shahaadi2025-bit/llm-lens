import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("scan_secrets", Path(__file__).resolve().parents[2] / "scripts" / "scan_secrets.py")
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)


def test_detects_real_looking_secrets():
    cases = {
        "neon": "DATABASE_URL=postgresql://neondb_owner:npg_AbCdEf1234567890@ep-x.neon.tech/db",
        "github": "token = ghp_" + "a" * 36,
        "openai": "key = sk-" + "b" * 30,
        "aws": "AKIAABCDEFGHIJKLMNOP",
        "pem": "-----BEGIN RSA PRIVATE KEY-----",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghij1234567890",
        "dburl": "postgresql://admin:s3cr3tValue99@db.internal/app",
    }
    for name, text in cases.items():
        assert scan.scan_text(f"{name}.txt", text), name


def test_placeholders_and_clean_text_pass():
    clean = ["postgresql+asyncpg://lens:change-me@db:5432/lens", "postgresql://user:password@localhost/x",
             "DATABASE_URL=postgresql://u:YOUR_PASSWORD@host/db", "plain prose with no secrets", "sk-short"]
    for text in clean:
        assert scan.scan_text("ok.txt", text) == [], text


def test_the_repository_itself_is_clean():
    assert scan.main() == 0
