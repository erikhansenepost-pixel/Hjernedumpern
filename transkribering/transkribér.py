#!/usr/bin/env python3
"""Transkribér lydfil lokalt med NB-Whisper.

Default-stack: MLX (Apple Silicon Metal-akselerert) med NB-Whisper-large.
Typisk 1x realtime på M1, ~2% WER på norsk. Gratis, privat, lokalt.

Bruk:
    ./transkribér.py <lydfil>
    ./transkribér.py <lydfil> --fast              # Turbo (8x raskere, ~3-4% WER, beta)
    ./transkribér.py <lydfil> --engine faster-whisper  # CPU fallback

For lange filer kan du bruke caffeinate så Mac ikke sover:
    caffeinate -i ./transkribér.py <lydfil>

Anti-hallu-defaults (mlx):
    --condition-on-previous-text=False   bryter spirale-loop-hallusinasjoner
    --hallu-silence-threshold=2.0        fjerner output i stille perioder >2s
    --initial-prompt(-file)              vokabular-priming (egennavn, fagord)
    Post-processing: trim_repetition_tail() fjerner end-of-stream-loops
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MLX_MODEL = "aalst/nb-whisper-large-mlx"
TURBO_MLX_MODEL = "aalst/nb-whisper-large-distil-turbo-beta-mlx"
DEFAULT_FW_MODEL = "NbAiLab/nb-whisper-large"
FW_FALLBACK_MODEL = "large-v3"


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg ikke funnet i PATH. Installer med: brew install ffmpeg")


def probe_duration(path: Path) -> float:
    if not shutil.which("ffprobe"):
        return 0.0
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(res.stdout.strip())
    except ValueError:
        return 0.0


def humansize(n: int) -> str:
    val = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if val < 1024:
            return f"{val:.1f} {unit}"
        val /= 1024
    return f"{val:.1f} TB"


def trim_repetition_tail(text: str, min_reps: int = 5, max_segment_chars: int = 200) -> str:
    """Fjern end-of-stream repetisjons-loops fra Whisper.

    Whisper hallusinerer noen ganger en gjentatt frase ved slutten av lydfilen
    (typisk etter outro-musikk eller stille). Skanner siste 1500 tegn etter
    en repeterende suffiks og trimmer av.
    """
    if not text:
        return text
    tail = text[-1500:]
    head = text[:-1500]

    for span in range(10, max_segment_chars + 1, 5):
        if span * min_reps > len(tail):
            continue
        candidate = tail[-span:]
        if not candidate.strip():
            continue
        check = tail
        reps = 0
        while check.endswith(candidate):
            reps += 1
            check = check[: -span]
            if reps >= min_reps + 5:
                break
        if reps >= min_reps:
            return (head + check).rstrip()
    return text


def transcribe_mlx(
    src: Path,
    model: str,
    language: str | None,
    verbose: bool,
    initial_prompt: str | None = None,
    condition_on_previous_text: bool = False,
    hallucination_silence_threshold: float | None = 2.0,
    word_timestamps: bool = False,
) -> tuple[str, str, list]:
    """Transkribér med MLX. Returnerer (tekst, detektert_språk, segmenter)."""
    import mlx.core as mx
    if not mx.metal.is_available():
        sys.exit("Metal er ikke tilgjengelig — MLX krever Apple Silicon. "
                 "Bruk --engine faster-whisper på Intel Mac.")

    import mlx_whisper
    result = mlx_whisper.transcribe(
        str(src),
        path_or_hf_repo=model,
        language=language,
        verbose=verbose,
        initial_prompt=initial_prompt,
        condition_on_previous_text=condition_on_previous_text,
        hallucination_silence_threshold=hallucination_silence_threshold,
        word_timestamps=word_timestamps,
    )
    return (
        result.get("text", "").strip(),
        result.get("language", "?"),
        result.get("segments", []),
    )


def transcribe_faster_whisper(
    src: Path, model: str, language: str | None, beam_size: int, vad: bool,
    initial_prompt: str | None = None,
) -> tuple[str, str]:
    """Transkribér med faster-whisper (CPU CTranslate2). Returnerer (tekst, språk)."""
    from faster_whisper import WhisperModel

    candidates = [model]
    if model == DEFAULT_FW_MODEL:
        candidates.append(FW_FALLBACK_MODEL)

    last_err: Exception | None = None
    whisper_model = None
    used = ""
    for name in candidates:
        try:
            print(f"Laster modell: {name} (device=cpu, compute=int8)")
            t0 = time.time()
            whisper_model = WhisperModel(name, device="cpu", compute_type="int8")
            used = name
            print(f"Modell klar på {time.time()-t0:.1f}s")
            break
        except Exception as e:
            last_err = e
            print(f"  Kunne ikke laste {name}: {e}", file=sys.stderr)
    if whisper_model is None:
        sys.exit(f"Ingen modell kunne lastes. Siste feil: {last_err}")

    segments_iter, info = whisper_model.transcribe(
        str(src),
        language=language,
        beam_size=beam_size,
        vad_filter=vad,
        initial_prompt=initial_prompt,
    )
    chunks = [seg.text.strip() for seg in segments_iter if seg.text]
    text = " ".join(chunks).strip()
    return text, info.language or "?"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transkribér lydfil lokalt med NB-Whisper (MLX default, faster-whisper fallback).",
    )
    parser.add_argument("input", type=Path, help="Sti til lydfil (m4a, mp3, wav, ogg, flac, webm, mp4)")
    parser.add_argument("--language", default="no",
                        help="Språkkode (default: no). Bruk 'auto' for auto-deteksjon.")
    parser.add_argument("--output", type=Path, help="Output-fil (default: <input>.txt)")
    parser.add_argument("--engine", choices=("mlx", "faster-whisper"), default="mlx",
                        help="Inferens-motor (default: mlx). faster-whisper = CPU fallback.")
    parser.add_argument("--fast", action="store_true",
                        help="MLX turbo-modell (8x raskere, men beta — har repetisjons-hallusinasjoner. "
                             "Default er kvalitetsmodell (NB-Whisper-large, ~2%% WER).")
    parser.add_argument("--model", help="Overstyr modell-navn (HuggingFace repo).")
    parser.add_argument("--verbose", action="store_true", help="MLX progress-logging.")
    parser.add_argument("--beam-size", type=int, default=5,
                        help="(faster-whisper) beam search width — default 5.")
    parser.add_argument("--no-vad", action="store_true",
                        help="(faster-whisper) skru av voice activity detection.")
    parser.add_argument("--initial-prompt", default=None,
                        help="Vokabular-priming: kommaseparert egennavn/fagord som hint til modellen.")
    parser.add_argument("--initial-prompt-file", type=Path, default=None,
                        help="Fil med initial_prompt (alternativ til --initial-prompt).")
    parser.add_argument("--condition-on-previous-text", action="store_true",
                        help="Mat forrige-segment-tekst inn i neste decode (kan gi spirale-hallu). "
                             "Default OFF for anti-hallu.")
    parser.add_argument("--hallu-silence-threshold", type=float, default=2.0,
                        help="MLX: drop output i stille perioder lengre enn dette (sek). 0 = av. Default 2.0.")
    parser.add_argument("--word-timestamps", action="store_true",
                        help="MLX: produser ord-nivå tidsstempler (litt langsommere).")
    parser.add_argument("--segments-output", type=Path,
                        help="Skriv segmenter (timestamp + tekst) til denne stien som JSONL.")
    parser.add_argument("--no-trim-repetitions", action="store_true",
                        help="Skru av automatisk fjerning av end-of-stream repetisjons-loops.")
    args = parser.parse_args()

    src: Path = args.input.expanduser().resolve()
    if not src.exists():
        sys.exit(f"Filen finnes ikke: {src}")
    if not src.is_file():
        sys.exit(f"Ikke en fil: {src}")

    require_ffmpeg()

    if args.model:
        model = args.model
    elif args.engine == "mlx":
        model = TURBO_MLX_MODEL if args.fast else DEFAULT_MLX_MODEL
    else:
        model = DEFAULT_FW_MODEL

    size = src.stat().st_size
    duration = probe_duration(src)
    out_path: Path = args.output.expanduser().resolve() if args.output else src.with_suffix(".txt")

    print(f"Input:    {src}")
    dur_str = f"{duration/60:.1f} min" if duration else "ukjent"
    print(f"Størrelse: {humansize(size)}  Varighet: {dur_str}")
    print(f"Output:   {out_path}")
    print(f"Motor:    {args.engine}  Modell: {model}  Språk: {args.language}")
    print()

    language = None if args.language == "auto" else args.language

    initial_prompt = args.initial_prompt
    if args.initial_prompt_file:
        ipf = args.initial_prompt_file.expanduser().resolve()
        if ipf.exists():
            initial_prompt = ipf.read_text(encoding="utf-8").strip()
        else:
            print(f"  WARN: initial-prompt-fil finnes ikke: {ipf}", file=sys.stderr)

    if initial_prompt:
        prompt_preview = initial_prompt[:120].replace("\n", " ")
        print(f"Initial prompt: {prompt_preview}{'...' if len(initial_prompt) > 120 else ''}")

    print(f"Transkriberer ({args.engine})...")
    t0 = time.time()
    segments: list = []
    if args.engine == "mlx":
        hallu_thresh = args.hallu_silence_threshold if args.hallu_silence_threshold > 0 else None
        text, detected, segments = transcribe_mlx(
            src, model, language, args.verbose,
            initial_prompt=initial_prompt,
            condition_on_previous_text=args.condition_on_previous_text,
            hallucination_silence_threshold=hallu_thresh,
            word_timestamps=args.word_timestamps,
        )
    else:
        text, detected = transcribe_faster_whisper(
            src, model, language, args.beam_size, vad=not args.no_vad,
            initial_prompt=initial_prompt,
        )
    elapsed = time.time() - t0

    # Post-process: fjern end-of-stream repetisjons-loops
    original_len = len(text)
    if not args.no_trim_repetitions:
        text = trim_repetition_tail(text)
        if len(text) < original_len:
            print(f"Trimmet {original_len - len(text)} tegn (end-of-stream repetisjons-loop)")

    out_path.write_text(text + "\n", encoding="utf-8")

    if args.segments_output and segments:
        import json as _json
        seg_path: Path = args.segments_output.expanduser().resolve()
        with seg_path.open("w", encoding="utf-8") as f:
            for seg in segments:
                f.write(_json.dumps({
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": seg.get("text", "").strip(),
                }, ensure_ascii=False) + "\n")
        print(f"Segmenter: {seg_path}")

    print()
    print(f"Ferdig — {len(text)} tegn skrevet til:")
    print(f"  {out_path}")
    print(f"Detektert språk: {detected}")
    if duration:
        speedup = duration / elapsed if elapsed > 0 else 0
        print(f"Prosess-tid: {elapsed:.1f}s  (audio-varighet: {duration:.1f}s "
              f"→ speedup {speedup:.2f}x)")
    else:
        print(f"Prosess-tid: {elapsed:.1f}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
