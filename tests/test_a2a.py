from __future__ import annotations

from vajra_gate.a2a import A2ABus


def test_message_count_property():
    bus = A2ABus()
    assert bus.message_count == 0
    bus.send("sender", "recipient", "hi")
    assert bus.message_count == 1


def test_message_count_never_exceeds_cap():
    bus = A2ABus(max_messages=3)
    for i in range(20):
        bus.send("sender", "recipient", f"msg {i}")
        assert bus.message_count <= 3


def test_send_prunes_oldest_read_messages_first():
    bus = A2ABus(max_messages=4)
    ids = [bus.send("sender", "recipient", f"m{i}").id for i in range(4)]
    bus.mark_read(ids[0])
    bus.mark_read(ids[2])
    bus.send("sender", "recipient", "m4")
    assert bus.message_count == 4
    remaining = [m.id for m in bus._messages]
    assert ids[0] not in remaining
    assert ids[1] in remaining
    assert ids[2] in remaining


def test_drops_oldest_unread_when_no_read_messages():
    bus = A2ABus(max_messages=2)
    ids = [bus.send("sender", "recipient", f"m{i}").id for i in range(5)]
    assert bus.message_count == 2
    remaining = [m.id for m in bus._messages]
    assert ids[0] not in remaining
    assert ids[1] not in remaining
    assert ids[2] not in remaining
    assert ids[3] in remaining
    assert ids[4] in remaining


def test_prunes_read_then_unread():
    bus = A2ABus(max_messages=3)
    ids = [bus.send("sender", "recipient", f"m{i}").id for i in range(4)]
    bus.mark_read(ids[0])
    for i in range(4, 7):
        bus.send("sender", "recipient", f"m{i}")
    assert bus.message_count == 3
    remaining = [m.id for m in bus._messages]
    assert ids[0] not in remaining
