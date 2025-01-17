import threading

import time
import unittest

from datetime import datetime

from pika.exchange_type import ExchangeType

from rabbitmq_client import (
    RMQConsumer,
    RMQProducer,
    ConsumeParams,
    QueueParams,
    ExchangeParams,
    ConsumeOK, ConfirmModeOK
)


def started(rmq_client, timeout=2.0):
    start_time = datetime.now()
    while not rmq_client.ready:
        elapsed_time = datetime.now() - start_time
        if elapsed_time.total_seconds() >= timeout:
            return False

        time.sleep(0.05)  # Wanne go fast

    return True


# noinspection DuplicatedCode
class IntegrationTest(unittest.TestCase):

    def setUp(self) -> None:
        self.consumer = RMQConsumer()
        self.consumer.start()
        self.assertTrue(started(self.consumer))

        self.producer = RMQProducer()
        self.producer.start()
        self.assertTrue(started(self.producer))

    def tearDown(self) -> None:
        self.consumer.stop()
        self.producer.stop()

    def test_stop_consumer(self):
        """
        Verify RMQConsumer, when stopped, shuts down completely and releases
        allocated resources.
        """
        # Run test
        self.consumer.stop()

        thread_count = len(threading.enumerate())
        # Only MainThread should still be running.
        self.assertEqual(2, thread_count)

    def test_consume_from_queue(self):
        """Verify RMQConsumer can consume from a queue."""
        msg_received = None
        event = threading.Event()

        def on_msg(msg):
            event.set()

            nonlocal msg_received
            msg_received = msg

        # Consume
        consume_key = self.consumer.consume(ConsumeParams(on_msg),
                                            queue_params=QueueParams("queue"))
        self.assertEqual(consume_key, "queue")

        # Wait for ConsumeOK
        event.wait(timeout=1.0)
        self.assertTrue(isinstance(msg_received, ConsumeOK))

        # Send a message and verify it is delivered OK
        event.clear()  # clear to re-use event
        self.producer.publish(b"body", queue_params=QueueParams("queue"))

        event.wait(timeout=1.0)
        self.assertEqual(msg_received, b"body")

    def test_consume_from_direct_exchange(self):
        """
        Verify RMQConsumer can consume from a direct exchange and routing key.
        """
        msg_received = None
        event = threading.Event()

        def on_msg(msg):
            event.set()

            nonlocal msg_received
            msg_received = msg

        # Consume
        consume_key = self.consumer.consume(
            ConsumeParams(on_msg),
            exchange_params=ExchangeParams("exchange"),
            routing_key="bla.bla"
        )
        self.assertEqual(consume_key, "exchange|bla.bla")

        # Wait for ConsumeOK
        event.wait(timeout=1.0)
        self.assertTrue(isinstance(msg_received, ConsumeOK))

        # Send a message and verify it is delivered OK
        event.clear()
        self.producer.publish(b"body",
                              exchange_params=ExchangeParams("exchange"),
                              routing_key="bla.bla")

        event.wait(timeout=1.0)
        self.assertEqual(msg_received, b"body")

    def test_consume_from_fanout_exchange(self):
        """
        Verify RMQConsumer can consume from a fanout exchange.
        """
        msg_received = None
        event = threading.Event()

        def on_msg(msg):
            event.set()

            nonlocal msg_received
            msg_received = msg

        # Consume
        consume_key = self.consumer.consume(
            ConsumeParams(on_msg),
            exchange_params=ExchangeParams("exchange_fanout",
                                           exchange_type=ExchangeType.fanout)
        )
        self.assertEqual(consume_key, "exchange_fanout")

        # Wait for ConsumeOK
        event.wait(timeout=1.0)
        self.assertTrue(isinstance(msg_received, ConsumeOK))

        # Send a message and verify it is delivered OK
        event.clear()
        self.producer.publish(
            b"body",
            exchange_params=ExchangeParams("exchange_fanout",
                                           exchange_type=ExchangeType.fanout))

        event.wait(timeout=1.0)
        self.assertEqual(msg_received, b"body")

    def test_consume_from_exchange_and_queue(self):
        """
        Verify RMQConsumer can consume from an exchange, binding it to a
        specific queue.
        """
        msg_received = None
        event = threading.Event()

        def on_msg(msg):
            event.set()

            nonlocal msg_received
            msg_received = msg

        # Consume
        consume_key = self.consumer.consume(
            ConsumeParams(on_msg),
            exchange_params=ExchangeParams("exchange_fanout",
                                           exchange_type=ExchangeType.fanout),
            queue_params=QueueParams("queue_fanout_receiver")
        )
        self.assertEqual(consume_key, "queue_fanout_receiver|exchange_fanout")

        # Wait for ConsumeOK
        event.wait(timeout=1.0)
        self.assertTrue(isinstance(msg_received, ConsumeOK))

        # Send a message and verify it is delivered OK
        event.clear()
        self.producer.publish(
            b"body",
            exchange_params=ExchangeParams("exchange_fanout",
                                           exchange_type=ExchangeType.fanout))

        event.wait(timeout=1.0)
        self.assertEqual(msg_received, b"body")

    def test_consume_from_exchange_routing_key_and_queue(self):
        """
        Verify RMQConsumer can consume from an exchange, binding it to a
        specific queue.
        """
        msg_received = None
        event = threading.Event()

        def on_msg(msg):
            event.set()

            nonlocal msg_received
            msg_received = msg

        # Consume
        consume_key = self.consumer.consume(
            ConsumeParams(on_msg),
            exchange_params=ExchangeParams("exchange_direct"),
            routing_key="fish",
            queue_params=QueueParams("queue_direct_receiver")
        )
        self.assertEqual(consume_key,
                         "queue_direct_receiver|exchange_direct|fish")

        # Wait for ConsumeOK
        event.wait(timeout=1.0)
        self.assertTrue(isinstance(msg_received, ConsumeOK))

        # Send a message and verify it is delivered OK
        event.clear()
        self.producer.publish(
            b"body",
            exchange_params=ExchangeParams("exchange_direct"),
            routing_key="fish"
        )

        event.wait(timeout=1.0)
        self.assertEqual(msg_received, b"body")

    def test_confirm_mode(self):
        """
        Verify confirm mode pushes publish_keys to users on successful
        delivery.
        """
        msg_received = None
        event = threading.Event()

        def on_confirm(confirm):
            event.set()

            nonlocal msg_received
            msg_received = confirm

        # Activate confirm mode
        self.producer.activate_confirm_mode(on_confirm)

        # Wait for ConfirmModeOK
        event.wait(timeout=1.0)
        self.assertTrue(isinstance(msg_received, ConfirmModeOK))

        # Send a message and verify it is delivered OK
        event.clear()
        publish_key = self.producer.publish(
            b"body",
            exchange_params=ExchangeParams("exchange_direct"),
        )

        event.wait(timeout=1.0)
        self.assertEqual(msg_received, publish_key)
        self.assertEqual(len(self.producer._unacked_publishes.keys()), 0)

    def test_buffer_publishes_with_confirm_mode_on(self):
        """
        Verify buffering publishes, with confirm mode on, and then starting the
        producer results in a correct number of messages being sent
        successfully, measured by counting and verifying the Basic.Acks
        received from the broker.
        """
        producer = RMQProducer()
        event = threading.Event()
        key_dict = dict()

        def on_confirm(confirm):
            if not isinstance(confirm, ConfirmModeOK):
                key_dict.pop(confirm)

            if len(key_dict.keys()) == 0:
                event.set()

        # Activate confirm mode
        producer.activate_confirm_mode(on_confirm)

        # Buffer a few publishes
        key_dict[
            producer.publish(
                b"body", exchange_params=ExchangeParams("exchange_direct"))
        ] = False
        key_dict[
            producer.publish(
                b"body", exchange_params=ExchangeParams("exchange_direct"))
        ] = False
        key_dict[
            producer.publish(
                b"body", exchange_params=ExchangeParams("exchange_direct"))
        ] = False
        self.assertEqual(len(producer._unacked_publishes.keys()), 0)
        self.assertEqual(len(producer._buffered_messages), 3)

        # Start the producer
        producer.start()
        self.assertTrue(started(producer))

        # Await all confirms
        event.wait(timeout=1.0)
        self.assertEqual(len(producer._unacked_publishes.keys()), 0)

        # Stop the extra producer
        producer.stop()

    @classmethod
    def tearDownClass(cls) -> None:
        """
        Need general teardown since not wanting to introduce waits part of
        test cases. Need to purge queues as consumer/producers are stopped
        before acking messages, sometimes.

        This teardown enabled re-testability without getting messages sent by
        a previous run.
        """
        client = RMQConsumer()
        client.start()
        assert started(client)

        client._channel.queue_purge("queue_fanout_receiver")
        client._channel.queue_purge("queue")

        client.stop()
