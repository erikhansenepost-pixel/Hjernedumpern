#!/usr/bin/env python3
"""Hjernedumpern voice-pipeline — orchestrerer transkribering + analyse + rendering.

Trigges av launchd WatchPaths når ny fil legges i iCloud-mappen Inn/.
Kan også kalles direkte: ./pipeline.py <fil>

Idempotent: sjekker state.sqlite før prosessering, og hopper over ferdig-
behandlede filer (via SHA-256 av innhold).

Hvis Claude CLI mangler (eller --no-analyse er gitt), kjører pipelinen
i transkripsjon-bare-modus og leverer kun rå tekst uten LLM-analyse.
"""
from __future__ import annotations

import argparse
import fcntl
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import analyse as analyse_mod
import config
import render
import state as state_mod

LOCK_FILE = config.PIPELINE_ROOT / ".pipeline.lock"


def _setup_logging() -> logging.Logger:
    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = config.LOGS_DIR / f"pipeline-{datetime.now().strftime('%Y-%m-%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    return logging.getLogger("pipeline")


log = _setup_logging()


def _probe_duration(audio: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip())
    except (ValueError, AttributeError):
        return None


def _transcribe(audio: Path, work_txt: Path) -> None:
    """Kall transkribér.py og skriv til work_txt."""
    if config.TRANSKRIBER_PY is None:
        raise RuntimeError(
            "transkribér.py ikke funnet. Sett HJERNEDUMPERN_TRANSKRIBER_PY "
            "eller plassér transkribering/ som søsken-mappe til voice-pipeline/."
        )
    cmd = [
        config.VENV_PYTHON, str(config.TRANSKRIBER_PY),
        str(audio), "--output", str(work_txt),
    ]
    log.info("Transkriberer: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    if result.returncode != 0:
        raise RuntimeError(
            f"transkribér.py feilet (exit {result.returncode}): "
            f"{result.stderr.strip()[:500]}"
        )
    if not work_txt.exists() or work_txt.stat().st_size == 0:
        raise RuntimeError(f"transkribér.py returnerte uten å skrive til {work_txt}")


_SLUG_OK = re.compile(r"[^a-z0-9-]+")


def _sanitize_slug(raw: str, fallback: str) -> str:
    """Tving slug til kebab-case ASCII, maks 60 tegn. Fall tilbake hvis tom."""
    if not raw:
        raw = fallback
    s = raw.strip().lower()
    s = (s.replace("æ", "ae").replace("ø", "o").replace("å", "aa")
           .replace("é", "e").replace("è", "e").replace("ü", "u")
           .replace(" ", "-").replace("_", "-"))
    s = _SLUG_OK.sub("-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        s = _SLUG_OK.sub("-", fallback.lower()).strip("-") or "opptak"
    return s[:60].rstrip("-")


def _build_out_stem(audio_mtime: float, fallback_stem: str, parsed: dict, outbox: Path) -> str:
    """YYYY-MM-DD-<slug> med kollisjonssuffix. Dato kommer fra audio-mtime
    pinned før evt. arkivering, så vi tåler race-conditions."""
    rec_date = datetime.fromtimestamp(audio_mtime).strftime("%Y-%m-%d")
    slug = _sanitize_slug(parsed.get("slug", ""), fallback_stem)
    base = f"{rec_date}-{slug}"
    candidate = base
    n = 2
    while any((outbox / f"{candidate}.{ext}").exists() for ext in ("md", "txt", "json")):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def _is_ready(audio: Path) -> bool:
    """Sjekk at fila er ferdig skrevet av iCloud (ikke placeholder/null-fil)."""
    if not audio.exists() or not audio.is_file():
        return False
    if audio.stat().st_size < config.MIN_AUDIO_BYTES:
        return False
    if audio.suffix.lower() not in config.AUDIO_SUFFIXES:
        return False
    # iCloud placeholder-filer har navnet `.foo.icloud` — de er skjult.
    # Men sjekk også at suffix ikke er .icloud.
    if audio.name.startswith(".") or ".icloud" in audio.name:
        return False
    return True


def process_file(audio: Path, state: state_mod.State, *, no_analyse: bool = False) -> Path | None:
    """Prosessér én lydfil. Returner sti til .md eller None hvis hoppet over.

    iCloud Drive-filer kopieres til lokal work-dir først for å unngå
    File Provider-framework-deadlock (EDEADLK).
    """
    log.info("=== Ny fil: %s ===", audio)

    if not _is_ready(audio):
        log.info("Fila er ikke klar (sync pågår eller ugyldig format): %s", audio)
        return None

    stem = audio.stem
    audio_mtime = audio.stat().st_mtime  # pin før evt. arkiv-flytting

    # Steg 0: Kopier til lokal work-dir FØR hashing/prosessering.
    # iCloud fs gir deadlock på fcntl/hash-lesing direkte.
    import tempfile
    work_root = config.LOGS_DIR / "work"
    work_root.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(prefix=f"{stem}-", dir=work_root))
    local_audio = work_dir / f"input{audio.suffix.lower()}"

    log.info("Kopierer til lokal work-dir: %s", local_audio)
    # iCloud File Provider gir EDEADLK når fcopyfile prøver xattrs samtidig som
    # fila materialiseres. `cp -X` skipper xattrs/ACLs og leser kun dataforken.
    # Forhåndskall til brctl download sikrer at fila er materialisert lokalt.
    if shutil.which("brctl"):
        subprocess.run(
            ["/usr/bin/brctl", "download", str(audio.parent)],
            capture_output=True, text=True, timeout=120,
        )
    cp = subprocess.run(
        ["/bin/cp", "-X", str(audio), str(local_audio)],
        capture_output=True, text=True, timeout=300,
    )
    if cp.returncode != 0 or not local_audio.exists():
        log.warning("/bin/cp -X feilet (%s), prøver byte-stream-fallback", cp.stderr.strip()[:200])
        with open(audio, "rb") as src_fh, open(local_audio, "wb") as dst_fh:
            shutil.copyfileobj(src_fh, dst_fh, length=1024 * 1024)
        if not local_audio.exists() or local_audio.stat().st_size == 0:
            raise RuntimeError(
                f"Kunne ikke kopiere fra iCloud (begge metoder feilet): "
                f"{cp.stderr.strip() or 'ukjent feil'}"
            )

    # Nå kan vi hashe trygt (lokal disk)
    if state.already_processed(local_audio):
        log.info("Allerede prosessert (hash-match), hopper over: %s", audio)
        shutil.rmtree(work_dir, ignore_errors=True)
        return None

    run_id = state.start(local_audio)
    work_txt = work_dir / f"{stem}.txt"
    work_json = work_dir / f"{stem}.json"
    work_md = work_dir / f"{stem}.md"

    duration = _probe_duration(local_audio)

    try:
        state.update(run_id, "transkriberer")
        t0 = time.time()
        _transcribe(local_audio, work_txt)
        log.info("Transkribering ferdig på %.1fs", time.time() - t0)

        do_analyse = (not no_analyse) and config.ANALYSE_AVAILABLE
        parsed: dict = {}
        analyse_note: str | None = None

        if do_analyse:
            state.update(run_id, "analyserer")
            t0 = time.time()
            try:
                parsed = analyse_mod.analyse(work_txt, work_json)
                log.info("Analyse ferdig på %.1fs", time.time() - t0)
            except analyse_mod.AnalyseUnavailable as e:
                log.warning("Analyse ikke tilgjengelig — fortsetter uten: %s", e)
                analyse_note = "_Analyse hoppet over: Claude CLI ikke tilgjengelig._"
        else:
            reason = "deaktivert med --no-analyse" if no_analyse else "Claude CLI ikke funnet"
            log.info("Hopper over analyse (%s)", reason)
            analyse_note = f"_Analyse hoppet over: {reason}._"

        state.update(run_id, "rendrer")
        transcript = work_txt.read_text(encoding="utf-8")

        # Flytt output til Ut/ med slug-basert navn (YYYY-MM-DD-<slug>),
        # lydfil til Arkiv/ med originalnavn beholdt.
        config.OUTBOX.mkdir(parents=True, exist_ok=True)
        config.ARCHIVE.mkdir(parents=True, exist_ok=True)
        out_stem = _build_out_stem(audio_mtime, stem, parsed, config.OUTBOX)
        log.info("Output-navn: %s (original: %s)", out_stem, stem)

        if parsed:
            md_content = render.render_md(out_stem, duration, transcript, parsed,
                                          original_name=stem)
        else:
            md_content = render.render_md_transcript_only(
                out_stem, duration, transcript, original_name=stem, note=analyse_note,
            )
        work_md.write_text(md_content, encoding="utf-8")

        final_txt = config.OUTBOX / f"{out_stem}.txt"
        final_md = config.OUTBOX / f"{out_stem}.md"
        shutil.move(str(work_txt), final_txt)
        shutil.move(str(work_md), final_md)
        if work_json.exists():
            final_json = config.OUTBOX / f"{out_stem}.json"
            shutil.move(str(work_json), final_json)

        archive_path = config.ARCHIVE / audio.name
        if archive_path.exists():
            archive_path = config.ARCHIVE / f"{stem}-{run_id}{audio.suffix}"
        # /bin/mv er File Provider-aware for iCloud
        mv = subprocess.run(
            ["/bin/mv", str(audio), str(archive_path)],
            capture_output=True, text=True, timeout=120,
        )
        if mv.returncode != 0:
            log.warning("Kunne ikke flytte til Arkiv/: %s", mv.stderr.strip())

        state.complete(run_id, final_md)
        log.info("Ferdig: %s", final_md)

        shutil.rmtree(work_dir, ignore_errors=True)
        return final_md

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        log.exception("FEIL i run %d: %s", run_id, err)
        state.fail(run_id, err)

        # Skriv feil-md til Ut/ så brukeren ser hva som gikk galt
        stage_map = {"transkriberer": "transkribering", "analyserer": "LLM-analyse",
                     "rendrer": "rendering"}
        current = state.conn.execute(
            "SELECT status FROM runs WHERE id = ?", (run_id,),
        ).fetchone()
        stage = stage_map.get(current[0] if current else "", "ukjent")

        error_md = config.OUTBOX / f"{stem}.error.md"
        config.OUTBOX.mkdir(parents=True, exist_ok=True)
        error_md.write_text(render.render_error_md(stem, err, stage), encoding="utf-8")
        return None


def _acquire_lock():
    """Global fil-lock så kun én pipeline-kjøring om gangen.
    Returner åpen file-descriptor hvis OK, None hvis allerede låst."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write(f"{datetime.now().isoformat()} pid={os.getpid()}\n")
        fd.flush()
        return fd
    except BlockingIOError:
        fd.close()
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Hjernedumpern voice-pipeline.")
    parser.add_argument(
        "inputs", nargs="*", type=Path,
        help="Fil(er) å prosessere. Uten argumenter scannes iCloud Inn/.",
    )
    parser.add_argument(
        "--no-analyse", action="store_true",
        help="Hopp over LLM-analyse-steget — kun transkripsjon.",
    )
    args = parser.parse_args()

    lock = _acquire_lock()
    if lock is None:
        log.info("Pipeline kjører allerede (global lock tatt) — avslutter stille.")
        return 0

    state = state_mod.State(config.STATE_DB)
    try:
        if args.inputs:
            candidates = [p.expanduser().resolve() for p in args.inputs]
        else:
            config.INBOX.mkdir(parents=True, exist_ok=True)
            candidates = sorted(
                p for p in config.INBOX.iterdir()
                if p.is_file() and p.suffix.lower() in config.AUDIO_SUFFIXES
            )

        if not candidates:
            log.info("Ingen filer å prosessere.")
            return 0

        # Kort pause så iCloud rekker å ferdigsynkronisere filer
        # skrevet i det øyeblikket launchd trigger.
        time.sleep(3)

        for audio in candidates:
            try:
                process_file(audio, state, no_analyse=args.no_analyse)
            except Exception:
                log.exception("Uhåndtert feil på %s", audio)

        return 0
    finally:
        state.close()
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
