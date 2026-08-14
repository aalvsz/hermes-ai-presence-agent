import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "content_queue.py"


def run(tmp_path, *args):
    env = os.environ.copy()
    env["HERMES_PRESENCE_RUNTIME"] = str(tmp_path)
    return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True, env=env)


def test_approval_is_bound_to_exact_draft(tmp_path):
    created = run(tmp_path, "enqueue", "--kind", "tweet", "--text", "A precise technical draft", "--source", "https://example.com")
    assert created.returncode == 0, created.stderr
    record = json.loads(created.stdout)
    rejected = run(tmp_path, "approve", record["id"], "--confirmation", "APPROVE POST wrong")
    assert rejected.returncode == 2
    approved = run(tmp_path, "approve", record["id"], "--confirmation", f"APPROVE POST {record['id']}")
    assert approved.returncode == 0, approved.stderr
    assert json.loads(approved.stdout)["state"] == "approved"


def test_tweet_length_is_bounded(tmp_path):
    result = run(tmp_path, "enqueue", "--kind", "tweet", "--text", "x" * 281)
    assert result.returncode == 2
    assert "maximum is 280" in result.stderr
