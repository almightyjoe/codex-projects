from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .collectors import ApiCollector, PublicCollector
from .database import EvidenceDatabase
from .evidence import EvidenceStore
from .exports import export_csvs
from .graphing import render_friend_graph
from .http_client import RequestManager
from .input_parser import parse_subject_input
from .models import CollectionResult, SteamInputError
from .paths import finalize_output_dir, make_output_dir
from .reports import write_reports


@dataclass(slots=True)
class RunOptions:
    targets: list[str]
    api_enabled: bool = False
    api_key: str = ""
    output_base: Path = Path("output")
    delay: float = 1.0
    retries: int = 3


def run_collection(
    options: RunOptions,
    progress: Callable[[str], None] | None = None,
    cancelled: threading.Event | None = None,
) -> list[CollectionResult]:
    targets = [target.strip() for target in options.targets if target.strip()]
    if not targets:
        raise SteamInputError("Enter at least one Steam target.")
    if options.api_enabled and not options.api_key.strip():
        raise SteamInputError("API mode selected, but no API key entered.")

    results: list[CollectionResult] = []
    for index, target in enumerate(targets, 1):
        if cancelled is not None and cancelled.is_set():
            break
        if progress:
            progress(f"[{index}/{len(targets)}] Preparing {target}")
        parsed = parse_subject_input(target)
        output_dir = make_output_dir(options.output_base, parsed["value"])
        evidence = EvidenceStore(output_dir)
        http = RequestManager(delay=options.delay, retries=options.retries, cancelled=cancelled)

        if options.api_enabled:
            collector = ApiCollector(http, evidence, options.api_key.strip())
            result = collector.collect(target, parsed, output_dir)
        else:
            collector = PublicCollector(http, evidence)
            result = collector.collect(target, parsed["url"], output_dir)

        final_dir = finalize_output_dir(options.output_base, result)
        evidence.output_dir = final_dir
        evidence.raw_dir = final_dir / "raw"
        evidence.media_dir = final_dir / "media"

        if progress:
            progress(f"[{index}/{len(targets)}] Writing exports for {target}")
        render_friend_graph(result)
        export_csvs(result)
        EvidenceDatabase(final_dir / "evidence.sqlite").write_result(result)
        evidence.write_manifest()
        write_reports(result)
        result.evidence = list(evidence.records)
        results.append(result)
        if progress:
            progress(f"[{index}/{len(targets)}] Finished {target}: {final_dir}")
    return results
