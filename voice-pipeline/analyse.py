"""LLM-analyse av transkripsjon via `claude --print` mot Sonnet.

Kaller Claude CLI med strukturert prompt og forventer JSON som svar.
Analysen er valgfri — hvis `claude` ikke finnes i PATH (eller
HJERNEDUMPERN_ANALYSE_DISABLED=1), hopper pipelinen over dette steget og
leverer kun transkripsjon.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import config


class AnalyseUnavailable(RuntimeError):
    """Claude CLI mangler eller analyse er deaktivert."""


def _load_prompt(transcript: str) -> str:
    prompt_template = (config.PROMPTS_DIR / "analyse.md").read_text(encoding="utf-8")
    return prompt_template.replace("{transcript}", transcript)


def _call_claude(prompt: str) -> str:
    """Kall claude --print og returner stdout. Raise ved feil."""
    result = subprocess.run(
        [config.CLAUDE_BIN, "--print", "--model", config.ANALYSE_MODEL, prompt],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"claude --print feilet (exit {result.returncode}): {result.stderr.strip()[:500]}"
        )
    return result.stdout.strip()


def _extract_json(text: str) -> dict:
    """Claude kan wrappe JSON i markdown-blokk. Håndter begge formater."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def analyse(transcript_path: Path, output_json: Path) -> dict:
    """Les transkripsjon, kall Claude, parse JSON, skriv til output_json.
    Returnerer parset dict. Raise ved endelig feil.

    Raises AnalyseUnavailable hvis Claude CLI mangler eller er deaktivert."""
    if not config.ANALYSE_AVAILABLE:
        raise AnalyseUnavailable(
            f"Claude CLI '{config.CLAUDE_BIN}' ikke funnet i PATH "
            "(eller HJERNEDUMPERN_ANALYSE_DISABLED=1). "
            "Installer Claude Code, eller kjør med --no-analyse."
        )

    transcript = transcript_path.read_text(encoding="utf-8").strip()
    if not transcript:
        raise ValueError(f"Transkripsjonen er tom: {transcript_path}")

    prompt = _load_prompt(transcript)

    last_err: Exception | None = None
    for attempt in range(1, config.ANALYSE_MAX_RETRIES + 1):
        try:
            raw = _call_claude(prompt)
            parsed = _extract_json(raw)
            output_json.write_text(
                json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            return parsed
        except (subprocess.TimeoutExpired, RuntimeError, json.JSONDecodeError) as e:
            last_err = e
            if attempt < config.ANALYSE_MAX_RETRIES:
                time.sleep(config.ANALYSE_RETRY_SLEEP_S)

    raise RuntimeError(
        f"Claude-analyse feilet etter {config.ANALYSE_MAX_RETRIES} forsøk: {last_err}"
    )
