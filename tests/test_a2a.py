# Tests for A2A (Agent-to-Agent) communication

import asyncio
import os
import pytest

# Set API key before imports to avoid RealtimeModel validation error
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-real")

from operators.base import BaseOperator
from operators.registry import (
    OperatorRegistry, A2ATask, A2AMessage,
    TaskStatus, MessagePriority,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class MockOperatorA(BaseOperator):
    """Test operator A."""
    def __init__(self, chat_ctx=None):
        super().__init__(
            instructions="I am Operator A.",
            chat_ctx=chat_ctx,
        )
        self.received_messages = []
        self.received_tasks = []

    async def handle_task(self, description, context):
        self.received_tasks.append(description)
        return {"result": f"A handled: {description}"}

    async def on_message(self, message):
        self.received_messages.append(message)


class MockOperatorB(BaseOperator):
    """Test operator B."""
    def __init__(self, chat_ctx=None):
        super().__init__(
            instructions="I am Operator B.",
            chat_ctx=chat_ctx,
        )
        self.received_messages = []

    async def handle_task(self, description, context):
        return {"result": f"B handled: {description}"}

    async def on_message(self, message):
        self.received_messages.append(message)


@pytest.fixture
def reg():
    """Fresh registry with two operators."""
    r = OperatorRegistry()
    r.register("alpha", MockOperatorA)
    r.register("beta", MockOperatorB)
    return r


# ---- Level 1: Swap ----

def test_swap_creates_new_operator(reg):
    op1 = reg.spawn("alpha")
    reg._instances["alpha"] = op1
    op2 = reg.swap("alpha", "beta")
    assert isinstance(op2, MockOperatorB)
    assert "alpha" not in reg._instances
    assert "beta" in reg._instances


def test_swap_returns_correct_type(reg):
    op = reg.swap("alpha", "beta")
    assert isinstance(op, MockOperatorB)


# ---- Level 2: Delegate ----

def test_delegate_creates_task(reg):
    task = _run(reg.delegate(
        from_operator="alpha",
        to_operator="beta",
        description="research pricing",
    ))
    assert isinstance(task, A2ATask)
    assert task.from_operator == "alpha"
    assert task.to_operator == "beta"
    assert task.description == "research pricing"
    assert task.status == TaskStatus.COMPLETED
    assert task.result["result"] == "B handled: research pricing"


def test_delegate_spawns_target_if_not_active(reg):
    assert "beta" not in reg._instances
    _run(reg.delegate("alpha", "beta", "do something"))
    assert "beta" in reg._instances


def test_delegate_task_tracked(reg):
    task = _run(reg.delegate("alpha", "beta", "test task"))
    retrieved = reg.get_task(task.id)
    assert retrieved is not None
    assert retrieved.status == TaskStatus.COMPLETED


def test_delegate_tasks_for_operator(reg):
    _run(reg.delegate("alpha", "beta", "task 1"))
    _run(reg.delegate("alpha", "beta", "task 2"))
    tasks = reg.get_tasks_for("alpha")
    assert len(tasks) == 2
    tasks_beta = reg.get_tasks_for("beta")
    assert len(tasks_beta) == 2  # same tasks, beta is the target


def test_delegate_timeout(reg):
    class SlowOperator(BaseOperator):
        def __init__(self, chat_ctx=None):
            super().__init__(instructions="slow", chat_ctx=chat_ctx)

        async def handle_task(self, description, context):
            await asyncio.sleep(10)
            return {"result": "done"}

    reg.register("slow", SlowOperator)
    task = _run(reg.delegate("alpha", "slow", "slow task", timeout=0.1))
    assert task.status == TaskStatus.FAILED
    assert "timed out" in task.error


# ---- Level 3: Message Bus ----

def test_direct_message(reg):
    # Spawn beta so it has an instance
    op_b = reg.spawn("beta")
    reg._instances["beta"] = op_b

    msg = _run(reg.message("alpha", to_operator="beta", body="hello"))
    assert isinstance(msg, A2AMessage)
    assert msg.from_operator == "alpha"
    assert msg.to_operator == "beta"
    assert len(op_b.received_messages) == 1
    assert op_b.received_messages[0].body == "hello"


def test_broadcast_message(reg):
    received = []

    def on_msg(msg):
        received.append(msg)

    reg.subscribe("research", on_msg)
    _run(reg.message("alpha", channel="research", body="new data"))
    assert len(received) == 1
    assert received[0].body == "new data"


def test_broadcast_multiple_subscribers(reg):
    received_a = []
    received_b = []

    reg.subscribe("updates", lambda m: received_a.append(m))
    reg.subscribe("updates", lambda m: received_b.append(m))

    _run(reg.message("alpha", channel="updates", body="broadcast"))
    assert len(received_a) == 1
    assert len(received_b) == 1


def test_unsubscribe(reg):
    received = []

    def handler(msg):
        received.append(msg)

    reg.subscribe("test", handler)
    _run(reg.message("alpha", channel="test", body="msg1"))
    assert len(received) == 1

    reg.unsubscribe("test", handler)
    _run(reg.message("alpha", channel="test", body="msg2"))
    assert len(received) == 1  # didn't receive second message


def test_get_active_operators(reg):
    assert reg.get_active_operators() == []
    reg._instances["alpha"] = reg.spawn("alpha")
    assert "alpha" in reg.get_active_operators()


# ---- BaseOperator A2A Methods ----

def test_operator_delegate_method(reg):
    """Operators can call self.delegate() which routes through registry."""
    op = reg.spawn("alpha")
    # The delegate method exists and is callable
    assert hasattr(op, 'delegate')
    assert asyncio.iscoroutinefunction(op.delegate)


def test_operator_message_method(reg):
    """Operators can call self.message() which routes through registry."""
    op = reg.spawn("alpha")
    assert hasattr(op, 'message')
    assert asyncio.iscoroutinefunction(op.message)


def test_operator_handle_task_method(reg):
    """Operators can override handle_task for delegated tasks."""
    op = reg.spawn("alpha")
    result = _run(op.handle_task("test task", {}))
    assert result["result"] == "A handled: test task"