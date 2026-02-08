from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx

from pokepocketpedia.ingest.pipeline import run_ingest
from pokepocketpedia.ingest.sources import parse_decks_table_from_html, parse_next_data_from_html


def _mock_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v2/en/series/tcgp":
        return httpx.Response(
            200,
            json={
                "id": "tcgp",
                "name": "TCG Pocket",
                "sets": [{"id": "A1", "name": "Genetic Apex"}],
            },
        )

    if request.url.path == "/v2/en/sets/A1":
        return httpx.Response(
            200,
            json={
                "id": "A1",
                "name": "Genetic Apex",
                "cards": [{"id": "A1-001"}, {"id": "A1-002"}],
            },
        )

    if request.url.path == "/v2/en/cards/A1-001":
        return httpx.Response(
            200,
            json={"id": "A1-001", "name": "Bulbasaur", "hp": 70, "set": {"id": "A1"}},
        )

    if request.url.path == "/v2/en/cards/A1-002":
        return httpx.Response(
            200,
            json={"id": "A1-002", "name": "Ivysaur", "hp": 90, "set": {"id": "A1"}},
        )

    if request.url.host == "play.limitlesstcg.com" and request.url.path == "/decks":
        html = """
        <html>
          <body>
            <div class="select-group">
              <select id="game"><option value="POCKET" selected>Pokemon TCG Pocket</option></select>
              <select id="format"><option value="STANDARD" selected>Standard</option></select>
              <select id="set"><option data-set="B2" selected>Fantastical Parade</option></select>
            </div>
            <p>65 tournaments, 9831 players, 26255 matches</p>
            <table class="meta">
              <tr>
                <th></th><th></th><th>Deck</th><th>Count</th><th>Share</th>
                <th>Score</th><th>Win %</th>
              </tr>
              <tr data-share="0.1512562302919337" data-winrate="0.534315404819002">
                <td>1</td>
                <td>
                  <img class="pokemon" src="https://r2.limitlesstcg.net/pokemon/gen9/hydreigon.png"/>
                  <img class="pokemon" src="https://r2.limitlesstcg.net/pokemon/gen9/absol-mega.png"/>
                </td>
                <td>
                  <a href="/decks/hydreigon-mega-absol-ex-b1">
                    Hydreigon Mega Absol ex
                  </a>
                </td>
                <td>1487</td>
                <td>15.13%</td>
                <td>
                  <a href="/decks/hydreigon-mega-absol-ex-b1/matchups">
                    4679 - 3817 - 261
                  </a>
                </td>
                <td>
                  <a href="/decks/hydreigon-mega-absol-ex-b1/matchups">
                    53.43%
                  </a>
                </td>
              </tr>
            </table>
            <script id="__NEXT_DATA__" type="application/json">
              {"props": {"pageProps": {"decks": [{"name": "Pikachu ex"}]}}}
            </script>
          </body>
        </html>
        """
        return httpx.Response(200, text=html)

    if request.url.host == "play.limitlesstcg.com" and request.url.path == (
        "/decks/hydreigon-mega-absol-ex-b1"
    ):
        html = """
        <html>
          <body>
            <table class="striped">
              <tr>
                <td><a href="/tournament/test123/player/alice/decklist">Alice</a></td>
              </tr>
              <tr>
                <td><a href="/tournament/test124/player/bob/decklist">Bob</a></td>
              </tr>
            </table>
          </body>
        </html>
        """
        return httpx.Response(200, text=html)

    if request.url.host == "play.limitlesstcg.com" and request.url.path == (
        "/tournament/test123/player/alice/decklist"
    ):
        hidden_input_value = (
            "[{&quot;count&quot;:2,&quot;name&quot;:&quot;Deino&quot;,&quot;set&quot;:&quot;B1&quot;,"
            "&quot;number&quot;:&quot;155&quot;},{&quot;count&quot;:1,"
            "&quot;name&quot;:&quot;Mega Absol ex&quot;,&quot;set&quot;:&quot;B1&quot;,"
            "&quot;number&quot;:&quot;151&quot;}]"
        )
        html = """
        <html>
          <body>
            <div class="decklist"></div>
            <form>
              <input type="hidden" name="input" value="__HIDDEN_INPUT__" />
            </form>
          </body>
        </html>
        """
        html = html.replace("__HIDDEN_INPUT__", hidden_input_value)
        return httpx.Response(200, text=html)

    if request.url.host == "play.limitlesstcg.com" and request.url.path == (
        "/tournament/test124/player/bob/decklist"
    ):
        hidden_input_value = (
            "[{&quot;count&quot;:1,&quot;name&quot;:&quot;Deino&quot;,&quot;set&quot;:&quot;B1&quot;,"
            "&quot;number&quot;:&quot;155&quot;},{&quot;count&quot;:1,"
            "&quot;name&quot;:&quot;Hydreigon&quot;,&quot;set&quot;:&quot;B1&quot;,"
            "&quot;number&quot;:&quot;157&quot;}]"
        )
        html = """
        <html>
          <body>
            <div class="decklist"></div>
            <form>
              <input type="hidden" name="input" value="__HIDDEN_INPUT__" />
            </form>
          </body>
        </html>
        """
        html = html.replace("__HIDDEN_INPUT__", hidden_input_value)
        return httpx.Response(200, text=html)

    return httpx.Response(404, text="not found")


def test_parse_next_data_from_html() -> None:
    html = '<script id="__NEXT_DATA__" type="application/json">{"ok":true}</script>'
    result = parse_next_data_from_html(html)
    assert result == {"ok": True}


def test_parse_decks_table_from_html() -> None:
    html = """
    <html>
      <select id="game"><option value="POCKET" selected>Pocket</option></select>
      <select id="format"><option value="STANDARD" selected>Standard</option></select>
      <select id="set"><option data-set="B2" selected>Fantastical Parade</option></select>
      <p>10 tournaments, 1234 players, 5678 matches</p>
      <table class="meta">
        <tr data-share="0.25" data-winrate="0.6">
          <td>1</td>
          <td><img class="pokemon" src="https://example.com/one.png"/></td>
          <td><a href="/decks/sample-deck?game=POCKET">Sample Deck</a></td>
          <td>100</td>
          <td>25.00%</td>
          <td><a href="/decks/sample-deck/matchups?game=POCKET">10 - 5 - 0</a></td>
          <td><a href="/decks/sample-deck/matchups?game=POCKET">60.00%</a></td>
        </tr>
      </table>
    </html>
    """
    parsed = parse_decks_table_from_html(html)
    assert parsed["overview"]["game"] == "POCKET"
    assert parsed["overview"]["set_code"] == "B2"
    assert parsed["overview"]["tournaments"] == 10
    assert len(parsed["decks"]) == 1
    assert parsed["decks"][0]["deck_name"] == "Sample Deck"
    assert parsed["decks"][0]["count"] == 100
    assert parsed["decks"][0]["share_pct"] == 25.0
    assert parsed["decks"][0]["win_rate_pct"] == 60.0


def test_run_ingest_success_writes_expected_files(tmp_path: Path) -> None:
    client = httpx.Client(transport=httpx.MockTransport(_mock_handler))
    report = run_ingest(
        raw_root=tmp_path / "raw",
        snapshot_date=date(2026, 2, 8),
        client=client,
        deck_detail_limit=None,
        decklist_samples_per_archetype=2,
    )

    assert report["status"] == "success"

    cards_file = tmp_path / "raw" / "cards" / "2026-02-08" / "cards.json"
    decks_file = tmp_path / "raw" / "decks" / "2026-02-08" / "decks.json"
    decks_html = tmp_path / "raw" / "decks" / "2026-02-08" / "decks_page.html"
    run_file = tmp_path / "raw" / "runs" / "2026-02-08" / "ingest_run.json"

    assert cards_file.exists()
    assert decks_file.exists()
    assert decks_html.exists()
    assert run_file.exists()

    cards_payload = json.loads(cards_file.read_text(encoding="utf-8"))
    decks_payload = json.loads(decks_file.read_text(encoding="utf-8"))
    run_payload = json.loads(run_file.read_text(encoding="utf-8"))

    assert cards_payload["series_payload"]["id"] == "tcgp"
    assert cards_payload["stats"]["set_count"] == 1
    assert cards_payload["stats"]["card_count"] == 2
    assert cards_payload["cards"][0]["id"] == "A1-001"
    assert cards_payload["cards"][0]["hp"] == 70

    assert decks_payload["has_next_data"] is True
    assert decks_payload["stats"]["deck_count"] == 1
    assert decks_payload["stats"]["deck_details_success_count"] == 1
    assert decks_payload["stats"]["decklist_samples_total"] == 2
    assert decks_payload["overview"]["game"] == "POCKET"
    assert decks_payload["decks"][0]["deck_name"] == "Hydreigon Mega Absol ex"
    assert decks_payload["decks"][0]["count"] == 1487
    assert decks_payload["decks"][0]["sample_decklist_count"] == 2
    assert len(decks_payload["decks"][0]["sample_decklist_urls"]) == 2
    assert decks_payload["decks"][0]["sample_deck_cards_count"] == 2.5
    assert decks_payload["decks"][0]["sample_deck_cards"][0]["name"] == "Deino"
    assert decks_payload["decks"][0]["sample_deck_cards"][0]["card_id"] == "B1-155"
    assert decks_payload["decks"][0]["sample_deck_cards"][0]["avg_count"] == 1.5
    assert decks_payload["next_data"]["props"]["pageProps"]["decks"][0]["name"] == "Pikachu ex"

    assert run_payload["status"] == "success"


def test_run_ingest_partial_failure(tmp_path: Path) -> None:
    def failing_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/en/series/tcgp":
            return httpx.Response(
                200,
                json={"id": "tcgp", "sets": [{"id": "A1"}]},
            )
        if request.url.path == "/v2/en/sets/A1":
            return httpx.Response(200, json={"id": "A1", "cards": [{"id": "A1-001"}]})
        if request.url.path == "/v2/en/cards/A1-001":
            return httpx.Response(200, json={"id": "A1-001", "name": "Bulbasaur"})
        return httpx.Response(500, text="server error")

    client = httpx.Client(transport=httpx.MockTransport(failing_handler))
    report = run_ingest(raw_root=tmp_path / "raw", snapshot_date=date(2026, 2, 8), client=client)

    assert report["status"] == "partial_failure"
    statuses = {item["source"]: item["status"] for item in report["sources"]}
    assert statuses["cards"] == "success"
    assert statuses["decks"] == "failed"

    cards_file = tmp_path / "raw" / "cards" / "2026-02-08" / "cards.json"
    run_file = tmp_path / "raw" / "runs" / "2026-02-08" / "ingest_run.json"

    assert cards_file.exists()
    assert run_file.exists()
