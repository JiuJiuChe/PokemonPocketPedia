from pokepocketpedia.recommend import llm_service


class _FakeBlock:
    def __init__(self, block_type: str, name: str | None = None, input_payload=None) -> None:
        self.type = block_type
        self.name = name
        self.input = input_payload


class _FakeMessage:
    def __init__(self, content) -> None:
        self.content = content


def test_extract_tool_input_prefers_submit_strategy_tool() -> None:
    message = _FakeMessage(
        content=[
            _FakeBlock(
                block_type="tool_use",
                name="code_execution",
                input_payload={"code": "print('hello')"},
            ),
            _FakeBlock(
                block_type="tool_use",
                name="submit_strategy",
                input_payload={"deck_gameplan": "ok"},
            ),
        ]
    )

    payload = llm_service._extract_tool_input(
        message,
        preferred_tool_name="submit_strategy",
    )

    assert payload == {"deck_gameplan": "ok"}
