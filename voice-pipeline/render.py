"""Render transkripsjon + analyse-JSON til lesbar .md."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import config


def _bullet_list(items: list) -> str:
    if not items:
        return "*(ingen)*"
    return "\n".join(f"- {x}" for x in items)


def _action_items(items: list[dict]) -> str:
    if not items:
        return "*(ingen)*"
    lines = []
    for it in items:
        hva = it.get("hva", "").strip()
        eier = it.get("eier", "uavklart").strip()
        når = it.get("når", "uavklart").strip()
        lines.append(f"- [ ] **{hva}** — eier: {eier}, når: {når}")
    return "\n".join(lines)


def render_md(
    audio_stem: str,
    duration_seconds: float | None,
    transcript: str,
    analyse: dict,
    generated_at: datetime | None = None,
    original_name: str | None = None,
) -> str:
    generated_at = generated_at or datetime.now().astimezone()
    word_count = len(transcript.split())
    duration_str = f"{duration_seconds/60:.1f} min" if duration_seconds else "ukjent"

    origin_line = (f"\n**Original:** {original_name}.m4a"
                   if original_name and original_name != audio_stem else "")

    md = f"""# {audio_stem}

**Lengde:** {duration_str}, {word_count} ord
**Transkribert:** {generated_at.strftime("%Y-%m-%d %H:%M")}
**Stemning:** {analyse.get("stemning", "uavklart")}{origin_line}

## Sammendrag

{analyse.get("sammendrag", "*(ikke generert)*").strip()}

## Hovedtemaer

{_bullet_list(analyse.get("hovedtemaer", []))}

## Beslutninger

{_bullet_list(analyse.get("beslutninger", []))}

## Action items

{_action_items(analyse.get("action_items", []))}

## Åpne spørsmål

{_bullet_list(analyse.get("åpne_spørsmål", []))}

## Personer nevnt

{_bullet_list(analyse.get("personer_nevnt", []))}

## Prosjekter nevnt

{_bullet_list(analyse.get("prosjekter_nevnt", []))}

## Oppfølging neste gang

{analyse.get("oppfølging_neste_gang", "*(ingen)*").strip()}

---

## Rå transkripsjon

{transcript.strip()}
"""
    return md


def render_md_transcript_only(
    audio_stem: str,
    duration_seconds: float | None,
    transcript: str,
    generated_at: datetime | None = None,
    original_name: str | None = None,
    note: str | None = None,
) -> str:
    """Markdown uten LLM-analyse — for når Claude CLI ikke er tilgjengelig."""
    generated_at = generated_at or datetime.now().astimezone()
    word_count = len(transcript.split())
    duration_str = f"{duration_seconds/60:.1f} min" if duration_seconds else "ukjent"

    origin_line = (f"\n**Original:** {original_name}.m4a"
                   if original_name and original_name != audio_stem else "")
    note_block = f"\n\n> {note}\n" if note else ""

    return f"""# {audio_stem}

**Lengde:** {duration_str}, {word_count} ord
**Transkribert:** {generated_at.strftime("%Y-%m-%d %H:%M")}{origin_line}{note_block}

## Transkripsjon

{transcript.strip()}
"""


def render_error_md(audio_stem: str, error: str, stage: str) -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    return f"""# {audio_stem} — FEIL

**Tidspunkt:** {now}
**Stadium:** {stage}

## Feilmelding

```
{error}
```

Sjekk logger i `{config.LOGS_DIR}` og `state.sqlite` for detaljer.
"""
