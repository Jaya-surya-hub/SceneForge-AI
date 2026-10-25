"""Tests for Typer CLI commands."""

from typer.testing import CliRunner
from signalroom.cli.main import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "IncuBrix Signal Room" in result.output
    assert "info" in result.output
    assert "health" in result.output
    assert "replay" in result.output
    assert "migrate" in result.output


def test_cli_info():
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "Runtime Configuration" in result.output
    assert "Version" in result.output


def test_cli_health():
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "Checking IncuBrix Signal Room health" in result.output
    assert "Database:" in result.output
    assert "Artifact Storage:" in result.output


def test_cli_replay_missing_question():
    result = runner.invoke(app, ["replay", "Q-NONEXISTENT", "--market", "US"])
    assert result.exit_code == 1
    assert "not found in Question Atlas" in result.output
