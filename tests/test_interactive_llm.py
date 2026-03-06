from pokepocketpedia.recommend import interactive_llm


class _FakeBlock:
    def __init__(self, block_type: str, name: str | None = None, input_payload=None) -> None:
        self.type = block_type
        self.name = name
        self.input = input_payload


class _FakeMessage:
    def __init__(self, content) -> None:
        self.content = content


def test_extract_tool_input_prefers_submit_analysis_tool() -> None:
    message = _FakeMessage(
        content=[
            _FakeBlock(
                block_type="tool_use",
                name="code_execution",
                input_payload={"code": "print('hello')"},
            ),
            _FakeBlock(
                block_type="tool_use",
                name="submit_interactive_analysis",
                input_payload={"executive_summary": "ok"},
            ),
        ]
    )

    payload = interactive_llm._extract_tool_input(
        message,
        preferred_tool_name="submit_interactive_analysis",
    )

    assert payload == {"executive_summary": "ok"}



def test_extract_chat_reply_falls_back_to_tool_input_text() -> None:
    message = _FakeMessage(
        content=[
            _FakeBlock(
                block_type="tool_use",
                name="code_execution",
                input_payload={"text": "Tool generated answer"},
            )
        ]
    )

    reply = interactive_llm._extract_chat_reply(message)

    assert reply == "Tool generated answer"
