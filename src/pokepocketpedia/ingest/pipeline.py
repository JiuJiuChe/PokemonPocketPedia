"""Phase 1 MVP ingestion pipeline."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from pokepocketpedia.ingest.sources import (
    LIMITLESS_POCKET_DECKS_URL,
    TCGDEX_CARD_URL_TEMPLATE,
    TCGDEX_POCKET_SERIES_URL,
    TCGDEX_SET_URL_TEMPLATE,
    extract_decklist_urls,
    fetch_json,
    fetch_text,
    parse_decklist_cards_from_html,
    parse_decks_table_from_html,
    parse_next_data_from_html,
)
from pokepocketpedia.storage.files import ensure_dir, write_json, write_text


@dataclass
class SourceResult:
    source: str
    status: str
    details: dict[str, Any]


class ProgressPrinter:
    """Minimal terminal progress bar for long-running ingest steps."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._last_line_len = 0
        self._last_percent_by_label: dict[str, int] = {}

    def update(self, label: str, current: int, total: int) -> None:
        if not self.enabled:
            return
        total = max(total, 1)
        ratio = max(0.0, min(1.0, current / total))
        width = 28
        filled = int(width * ratio)
        bar = "=" * filled + "-" * (width - filled)
        percent = int(ratio * 100)
        previous_percent = self._last_percent_by_label.get(label)
        if current not in {1, total} and previous_percent == percent:
            return

        line = f"{label:<20} [{bar}] {current:>4}/{total:<4} {percent:>3}%"
        padding = " " * max(0, self._last_line_len - len(line))
        print(f"\r{line}{padding}", end="", file=sys.stderr, flush=True)
        self._last_line_len = len(line)
        self._last_percent_by_label[label] = percent

    def step(self, message: str) -> None:
        if not self.enabled:
            return
        print(message, file=sys.stderr, flush=True)

    def done(self) -> None:
        if not self.enabled:
            return
        print(file=sys.stderr, flush=True)
        self._last_line_len = 0


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _snapshot_date(value: date | None = None) -> str:
    return (value or date.today()).isoformat()


def _build_raw_dirs(raw_root: Path, snapshot_date: str) -> dict[str, Path]:
    return {
        "cards": raw_root / "cards" / snapshot_date,
        "decks": raw_root / "decks" / snapshot_date,
        "runs": raw_root / "runs" / snapshot_date,
    }


def _ingest_cards(
    client: httpx.Client,
    cards_dir: Path,
    snapshot_date: str,
    progress: ProgressPrinter,
) -> SourceResult:
    fetched_at = _utc_now_iso()
    progress.step("[ingest] cards: fetching Pocket series metadata")
    series_payload = fetch_json(client, TCGDEX_POCKET_SERIES_URL)
    set_entries = series_payload.get("sets", [])
    if not isinstance(set_entries, list):
        raise ValueError("TCGdex series payload did not include a list of sets.")

    set_ids: list[str] = []
    seen_set_ids: set[str] = set()
    for item in set_entries:
        set_id: str | None
        if isinstance(item, dict):
            raw_id = item.get("id")
            set_id = str(raw_id) if raw_id else None
        elif isinstance(item, str):
            set_id = item
        else:
            set_id = None

        if set_id and set_id not in seen_set_ids:
            seen_set_ids.add(set_id)
            set_ids.append(set_id)

    if not set_ids:
        raise ValueError("No Pocket set ids were found in the TCGdex series payload.")

    set_payloads: list[dict[str, Any]] = []
    card_ids: list[str] = []
    seen_card_ids: set[str] = set()
    for idx, set_id in enumerate(set_ids, start=1):
        set_payload = fetch_json(client, TCGDEX_SET_URL_TEMPLATE.format(set_id=set_id))
        set_payloads.append(set_payload)
        progress.update("cards: sets", idx, len(set_ids))

        cards_in_set = set_payload.get("cards", [])
        if not isinstance(cards_in_set, list):
            continue

        for card_item in cards_in_set:
            card_id: str | None
            if isinstance(card_item, dict):
                raw_id = card_item.get("id")
                card_id = str(raw_id) if raw_id else None
            elif isinstance(card_item, str):
                card_id = card_item
            else:
                card_id = None

            if card_id and card_id not in seen_card_ids:
                seen_card_ids.add(card_id)
                card_ids.append(card_id)

    if not card_ids:
        raise ValueError("No card ids were found while traversing Pocket sets.")

    progress.done()
    progress.step("[ingest] cards: fetching card details")
    card_payloads: list[dict[str, Any]] = []
    for idx, card_id in enumerate(card_ids, start=1):
        card_payloads.append(fetch_json(client, TCGDEX_CARD_URL_TEMPLATE.format(card_id=card_id)))
        progress.update("cards: details", idx, len(card_ids))
    progress.done()

    payload = {
        "snapshot_date": snapshot_date,
        "source": "tcgdex",
        "series": "tcgp",
        "source_url": TCGDEX_POCKET_SERIES_URL,
        "fetched_at": fetched_at,
        "series_payload": series_payload,
        "sets": set_payloads,
        "cards": card_payloads,
        "stats": {
            "set_count": len(set_payloads),
            "card_count": len(card_payloads),
        },
    }
    write_json(cards_dir / "cards.json", payload)

    return SourceResult(
        source="cards",
        status="success",
        details={
            "source_url": TCGDEX_POCKET_SERIES_URL,
            "fetched_at": fetched_at,
            "output_file": str(cards_dir / "cards.json"),
            "set_count": len(set_payloads),
            "card_count": len(card_payloads),
        },
    )


def _ingest_decks(
    client: httpx.Client,
    decks_dir: Path,
    snapshot_date: str,
    progress: ProgressPrinter,
    deck_detail_limit: int | None,
    decklist_samples_per_archetype: int,
) -> SourceResult:
    fetched_at = _utc_now_iso()
    progress.step("[ingest] decks: fetching page")
    page_html = fetch_text(client, LIMITLESS_POCKET_DECKS_URL)
    progress.update("decks: fetch", 1, 3)
    next_data = parse_next_data_from_html(page_html)
    progress.update("decks: parse", 2, 3)
    parsed_table = parse_decks_table_from_html(page_html)
    progress.update("decks: write", 3, 3)
    progress.done()

    decks = parsed_table["decks"]
    details_target = decks if deck_detail_limit is None else decks[:deck_detail_limit]
    progress.step("[ingest] decks: fetching sample decklists")
    details_success = 0
    details_failed = 0
    sampled_decklists_total = 0
    for idx, deck in enumerate(details_target, start=1):
        deck_url = deck.get("deck_url")
        if not deck_url:
            details_failed += 1
            progress.update("decks: details", idx, len(details_target))
            continue

        try:
            archetype_html = fetch_text(client, deck_url)
            decklist_urls = extract_decklist_urls(
                archetype_html,
                limit=decklist_samples_per_archetype,
            )
            if not decklist_urls:
                deck["sample_decklist_url"] = None
                deck["sample_decklist_urls"] = []
                deck["sample_deck_cards"] = []
                deck["sample_deck_cards_count"] = 0
                deck["sample_decklist_count"] = 0
                details_failed += 1
                progress.update("decks: details", idx, len(details_target))
                continue

            sampled_decklists_total += len(decklist_urls)
            sampled_lists: list[list[dict[str, Any]]] = []
            for decklist_url in decklist_urls:
                decklist_html = fetch_text(client, decklist_url)
                sampled_lists.append(parse_decklist_cards_from_html(decklist_html))

            aggregated_cards = _aggregate_sample_cards(sampled_lists)
            deck["sample_decklist_url"] = decklist_urls[0]
            deck["sample_decklist_urls"] = decklist_urls
            deck["sample_deck_cards"] = aggregated_cards
            deck["sample_deck_cards_count"] = sum(
                item.get("avg_count", 0.0) for item in aggregated_cards
            )
            deck["sample_decklist_count"] = len(decklist_urls)
            details_success += 1
        except Exception:
            deck["sample_decklist_url"] = None
            deck["sample_decklist_urls"] = []
            deck["sample_deck_cards"] = []
            deck["sample_deck_cards_count"] = 0
            deck["sample_decklist_count"] = 0
            details_failed += 1

        progress.update("decks: details", idx, len(details_target))
    progress.done()

    write_text(decks_dir / "decks_page.html", page_html)

    payload = {
        "snapshot_date": snapshot_date,
        "source": "limitless",
        "source_url": LIMITLESS_POCKET_DECKS_URL,
        "fetched_at": fetched_at,
        "has_next_data": next_data is not None,
        "next_data": next_data,
        "overview": parsed_table["overview"],
        "decks": decks,
        "stats": {
            "deck_count": len(decks),
            "deck_details_target_count": len(details_target),
            "deck_details_success_count": details_success,
            "deck_details_failed_count": details_failed,
            "decklist_samples_per_archetype": decklist_samples_per_archetype,
            "decklist_samples_total": sampled_decklists_total,
        },
    }
    write_json(decks_dir / "decks.json", payload)

    return SourceResult(
        source="decks",
        status="success",
        details={
            "source_url": LIMITLESS_POCKET_DECKS_URL,
            "fetched_at": fetched_at,
            "output_files": [str(decks_dir / "decks_page.html"), str(decks_dir / "decks.json")],
            "has_next_data": next_data is not None,
            "deck_count": len(decks),
            "deck_details_target_count": len(details_target),
            "deck_details_success_count": details_success,
            "deck_details_failed_count": details_failed,
            "decklist_samples_per_archetype": decklist_samples_per_archetype,
            "decklist_samples_total": sampled_decklists_total,
        },
    )


def _aggregate_sample_cards(sampled_lists: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    sample_count = len(sampled_lists)
    if sample_count == 0:
        return []

    aggregated: dict[str, dict[str, Any]] = {}
    for cards in sampled_lists:
        seen_in_list: set[str] = set()
        for item in cards:
            card_id = item.get("card_id")
            name = item.get("name")
            key = str(card_id) if card_id else f"name:{name}"
            if key not in aggregated:
                aggregated[key] = {
                    "card_id": card_id,
                    "card_url": item.get("card_url"),
                    "name": name,
                    "set_code": item.get("set_code"),
                    "number": item.get("number"),
                    "total_count": 0,
                    "present_in_samples": 0,
                }

            count_value = item.get("count")
            if isinstance(count_value, int):
                aggregated[key]["total_count"] += count_value

            if key not in seen_in_list:
                seen_in_list.add(key)
                aggregated[key]["present_in_samples"] += 1

    result: list[dict[str, Any]] = []
    for value in aggregated.values():
        total_count = value["total_count"]
        present_in_samples = value["present_in_samples"]
        avg_count = total_count / sample_count
        result.append(
            {
                "card_id": value["card_id"],
                "card_url": value["card_url"],
                "name": value["name"],
                "set_code": value["set_code"],
                "number": value["number"],
                "sample_count": sample_count,
                "present_in_samples": present_in_samples,
                "presence_rate": present_in_samples / sample_count,
                "total_count": total_count,
                "avg_count": round(avg_count, 4),
            }
        )

    result.sort(
        key=lambda item: (
            -(item.get("avg_count") or 0.0),
            -(item.get("presence_rate") or 0.0),
            str(item.get("name") or ""),
        )
    )
    return result


def run_ingest(
    raw_root: Path = Path("data/raw"),
    snapshot_date: date | None = None,
    client: httpx.Client | None = None,
    show_progress: bool = True,
    deck_detail_limit: int | None = 100,
    decklist_samples_per_archetype: int = 3,
) -> dict[str, Any]:
    date_value = _snapshot_date(snapshot_date)
    dirs = _build_raw_dirs(raw_root, date_value)
    for path in dirs.values():
        ensure_dir(path)

    owned_client = False
    if client is None:
        client = httpx.Client()
        owned_client = True

    results: list[SourceResult] = []
    progress = ProgressPrinter(enabled=show_progress)

    try:
        try:
            results.append(_ingest_cards(client, dirs["cards"], date_value, progress))
        except Exception as exc:  # pragma: no cover - exercised by error test.
            progress.done()
            results.append(
                SourceResult(
                    source="cards",
                    status="failed",
                    details={"error": str(exc), "source_url": TCGDEX_POCKET_SERIES_URL},
                )
            )

        try:
            results.append(
                _ingest_decks(
                    client,
                    dirs["decks"],
                    date_value,
                    progress,
                    deck_detail_limit,
                    decklist_samples_per_archetype,
                )
            )
        except Exception as exc:  # pragma: no cover - exercised by error test.
            progress.done()
            results.append(
                SourceResult(
                    source="decks",
                    status="failed",
                    details={"error": str(exc), "source_url": LIMITLESS_POCKET_DECKS_URL},
                )
            )
    finally:
        if owned_client:
            client.close()

    failed = [item for item in results if item.status != "success"]
    run_status = "success" if not failed else "partial_failure"

    report = {
        "snapshot_date": date_value,
        "ran_at": _utc_now_iso(),
        "status": run_status,
        "sources": [
            {"source": item.source, "status": item.status, "details": item.details}
            for item in results
        ],
    }

    write_json(dirs["runs"] / "ingest_run.json", report)
    return report
