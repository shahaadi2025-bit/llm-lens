"""CLI tests run the real command line in --local mode (own SQLite file, in-process app). Sync tests: the CLI owns its event loop."""
import json
from pathlib import Path

import pytest
import yaml

from app.cli.main import main
from app.cli.templates import TemplateError, load_template

SMALL = {"name": "cli small", "task_type": "arithmetic_representation", "model": "mock-deterministic-v1", "seed": 5,
         "config": {"n_random_pairs": 1}}  # 2 pairs x 6 forms = 12 runs


@pytest.fixture
def cli(tmp_path, monkeypatch, capsys):  # noqa: ANN201
    """Returns run(*argv) -> (exit_code, stdout, stderr), isolated to a temp database."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'x.sqlite'}")  # restored after the test
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr("app.cli.main.TOKEN_FILE", tmp_path / ".llm-lens" / "token")
    db = str(tmp_path / "cli.sqlite")

    def run(*argv: str) -> tuple[int, str, str]:
        capsys.readouterr()
        code = main(["--local", "--db", db, *argv])
        out = capsys.readouterr()
        return code, out.out, out.err

    yield run
    # The CLI's local mode caches settings built from this test's environment; never let that leak into other tests.
    from app.api.deps import get_adapter, get_engine
    from app.core.config import get_settings

    for fn in (get_settings, get_adapter, get_engine):
        fn.cache_clear()


def write_template(tmp_path: Path, **over) -> str:
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump({**SMALL, **over}))
    return str(p)


def test_health_labels_mock_mode(cli):
    code, out, _ = cli("health")
    assert code == 0 and "status: ok" in out and "DEMO / MOCK DATA" in out


def test_run_list_inspect_report_export_roundtrip(cli, tmp_path):
    code, out, err = cli("run", write_template(tmp_path), "--report", str(tmp_path / "r.md"))
    assert code == 0, err
    assert "12/12 runs finished (completed)" in out and "accuracy" in out and "95% CI [" in out and "wilson-95" in out
    assert "DEMO / MOCK DATA" in out and (tmp_path / "r.md").read_text().count("\n## ") == 14

    code, out, _ = cli("list")
    assert code == 0 and "cli small" in out and "[DEMO]" in out and "completed" in out
    assert cli("list", "--status", "failed")[1].strip() == "no experiments"
    exp_id = out.split("\n")[1].split()[0]

    code, out, _ = cli("inspect", exp_id, "--runs")
    assert code == 0 and "question:" in out and out.count("expected ") == 12 and "evaluator numeric_match" in out

    code, out, _ = cli("report", exp_id, "-o", str(tmp_path / "again.md"))
    assert code == 0 and "report written" in out and "# Research report: cli small" in (tmp_path / "again.md").read_text()

    code, _, _ = cli("export", exp_id, "--format", "json", "-o", str(tmp_path / "e.json"))
    bundle = json.loads((tmp_path / "e.json").read_text())
    assert code == 0 and len(bundle["runs"]) == 12 and bundle["export"]["contains_demo_data"] is True
    code, _, _ = cli("export", exp_id, "--format", "csv", "-o", str(tmp_path / "e.csv"))
    assert code == 0 and (tmp_path / "e.csv").read_text().count("\n") == 13  # header + 12 runs


def test_run_no_wait_and_status_filter(cli, tmp_path):
    code, out, _ = cli("run", write_template(tmp_path, name="async one"), "--no-wait")
    assert code == 0 and "started; check with: llm-lens inspect" in out


def test_compare_needs_matched_designs_then_reports_a_difference_without_a_cause(cli, tmp_path):
    a = write_template(tmp_path, name="A", model="mock-deterministic-v1", seed=11, config={"n_random_pairs": 5})
    cli("run", a)
    code, out, _ = cli("compare", "mock-deterministic-v1", "mock-deterministic-v2")
    assert code == 1 and "not comparable" in out  # model B has no matching experiment yet
    cli("run", write_template(tmp_path, name="B", model="mock-deterministic-v2", seed=11, config={"n_random_pairs": 5}))
    code, out, _ = cli("compare", "mock-deterministic-v1", "mock-deterministic-v2")
    assert code == 0 and "matched experiment pair" in out and "DEMO / MOCK DATA" in out
    assert "does not say what changed" in out or "compatible with no difference" in out
    assert "because" not in out.lower() and "caused" not in out.lower()
    assert cli("compare", "mock-deterministic-v1@mock-1", "mock-deterministic-v2@mock-2")[0] == 0  # slug@version works


def test_errors_exit_with_code_2_and_a_clear_message(cli, tmp_path):
    code, _, err = cli("run", str(tmp_path / "missing.yaml"))
    assert code == 2 and "template not found" in err
    code, _, err = cli("compare", "nope", "mock-deterministic-v1")
    assert code == 2 and "unknown model version" in err and "mock-deterministic-v1@mock-1" in err
    code, _, err = cli("inspect", "00000000-0000-0000-0000-000000000000")
    assert code == 2 and "404" in err
    bad = write_template(tmp_path, config={"n_random_pairs": 999})
    code, _, err = cli("run", bad)
    assert code == 2 and "n_random_pairs" in err


def test_unreachable_server_is_reported_not_a_traceback(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr("app.cli.main.TOKEN_FILE", tmp_path / "none")
    code = main(["--api", "http://127.0.0.1:9", "health"])
    err = capsys.readouterr().err
    assert code == 2 and "cannot reach the server" in err and "Traceback" not in err


def test_templates_are_validated_and_parsed_safely(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text(yaml.safe_dump(SMALL))
    body = load_template(str(p))
    assert body["model_slug"] == "mock-deterministic-v1" and "model" not in body and body["config"] == {"n_random_pairs": 1}
    for text, msg in (("- a\n- b", "mapping"), ("name: x\n", "task_type"), ("name: x\ntask_type: t\nbogus: 1", "unknown template keys"),
                      ("name: x\ntask_type: t\nconfig: 5", "config"), ("name: [unclosed", "invalid YAML"),
                      ("name: !!python/object/apply:os.system ['echo pwned']\ntask_type: t", "invalid YAML")):  # no code execution
        p.write_text(text)
        with pytest.raises(TemplateError, match=msg):
            load_template(str(p))


def test_shipped_templates_are_valid():
    root = Path(__file__).resolve().parents[2] / "experiments" / "templates"
    files = sorted(root.glob("*.yaml"))
    assert len(files) >= 7
    for f in files:
        body = load_template(str(f))
        assert body["task_type"] in ("arithmetic_representation", "prompt_sensitivity", "instruction_ordering", "context_position",
                                     "context_length") and body.get("research_question")


def test_seed_demo_populates_every_page_idempotently_and_labels_it(cli):
    code, out, err = cli("seed-demo")
    assert code == 0, err
    assert out.count("created  ") >= 7 and "follow-up experiment" in out and "research report" in out and "DEMO / MOCK DATA" in out
    code, out, _ = cli("list")
    assert out.count("[DEMO]") == out.count("Demo: ") >= 3 or "Demo: " in out
    code, out, _ = cli("seed-demo")  # second run: nothing new
    assert code == 0 and "demo data already present" in out and "created" not in out


def test_seed_demo_refuses_on_a_real_model_deployment(cli, monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    code, _, err = cli("seed-demo")
    assert code == 2 and "only seeded on mock deployments" in err
