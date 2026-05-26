from __future__ import annotations

import pytest

from prc.llm import MockLLMClient, MockLLMExhausted


async def test_mock_plays_back_in_order() -> None:
    mock = MockLLMClient()
    mock.queue("first")
    mock.queue("second")
    r1 = await mock.complete("sys", [{"role": "user", "content": "a"}])
    r2 = await mock.complete("sys", [{"role": "user", "content": "b"}])
    assert r1.content == "first"
    assert r2.content == "second"
    assert len(mock.calls) == 2


async def test_mock_raises_when_exhausted() -> None:
    mock = MockLLMClient()
    with pytest.raises(MockLLMExhausted):
        await mock.complete("sys", [])
