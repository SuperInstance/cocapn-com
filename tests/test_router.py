"""Tests for cocapn_com.router."""

from cocapn_com.channel import Channel, ChannelMode
from cocapn_com.message import Message, MessageType, Priority
from cocapn_com.router import DeliveryRule, MessageRouter


class TestDeliveryRule:
    def test_match_all(self):
        rule = DeliveryRule()
        msg = Message(sender="a", recipient="b", payload="x")
        assert rule.matches(msg)

    def test_source_pattern(self):
        rule = DeliveryRule(source_pattern="agent-*")
        assert rule.matches(Message(sender="agent-1", recipient="b", payload="x"))
        assert not rule.matches(Message(sender="other", recipient="b", payload="x"))

    def test_dest_pattern(self):
        rule = DeliveryRule(dest_pattern="service-*")
        assert rule.matches(Message(sender="a", recipient="service-x", payload="x"))
        assert not rule.matches(Message(sender="a", recipient="other", payload="x"))

    def test_type_filter(self):
        rule = DeliveryRule(types=[MessageType.COMMAND, MessageType.QUERY])
        assert rule.matches(Message(sender="a", recipient="b", payload="x", type=MessageType.COMMAND))
        assert not rule.matches(Message(sender="a", recipient="b", payload="x", type=MessageType.TEXT))

    def test_custom_filter(self):
        rule = DeliveryRule(filter_fn=lambda m: m.priority == Priority.HIGH)
        assert rule.matches(Message(sender="a", recipient="b", payload="x", priority=Priority.HIGH))
        assert not rule.matches(Message(sender="a", recipient="b", payload="x", priority=Priority.LOW))

    def test_disabled(self):
        rule = DeliveryRule(enabled=False)
        assert not rule.matches(Message(sender="a", recipient="b", payload="x"))


class TestMessageRouter:
    def test_default_channel_delivers(self):
        router = MessageRouter()
        received: list[Message] = []
        router._default_channel.subscribe("b", lambda m: received.append(m))
        msg = Message(sender="a", recipient="b", payload="hello")
        results = router.route(msg)
        assert "default" in results
        assert len(received) == 1

    def test_rule_routes_to_named_channel(self):
        router = MessageRouter()
        alerts = Channel("alerts", ChannelMode.PUB_SUB)
        router.add_channel(alerts)

        received: list[Message] = []
        alerts.subscribe("ops", lambda m: received.append(m))

        router.add_rule(DeliveryRule(
            types=[MessageType.ERROR],
            channel_name="alerts",
        ))

        msg = Message(sender="a", recipient="b", payload="fail", type=MessageType.ERROR)
        results = router.route(msg)
        assert "alerts" in results
        assert len(received) == 1

    def test_forward_to_agents(self):
        router = MessageRouter()
        received: list[Message] = []
        router._default_channel.subscribe("logger", lambda m: received.append(m))

        router.add_rule(DeliveryRule(
            forward_to=["logger"],
        ))

        msg = Message(sender="a", recipient="b", payload="hi")
        results = router.route(msg)
        assert "default" in results
        assert any(r.recipient == "logger" for r in received)

    def test_remove_channel(self):
        router = MessageRouter()
        ch = Channel("temp")
        router.add_channel(ch)
        assert router.get_channel("temp") is ch
        router.remove_channel("temp")
        assert router.get_channel("temp") is None

    def test_cannot_remove_default(self):
        router = MessageRouter()
        import pytest
        with pytest.raises(ValueError):
            router.remove_channel("default")

    def test_clear_rules(self):
        router = MessageRouter()
        router.add_rule(DeliveryRule(source_pattern="x"))
        router.add_rule(DeliveryRule(source_pattern="y"))
        router.clear_rules()
        assert len(router._rules) == 0
