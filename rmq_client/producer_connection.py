import logging
import signal

from threading import Thread
from multiprocessing import Queue as IPCQueue

from .producer_channel import RMQProducerChannel
from .log import LogItem
from .connection import RMQConnection


def create_producer_connection(work_queue, log_queue):
    """
    Interface function to instantiate and connect a producer connection. This
    function is intended as a target for a new process to avoid having to
    instantiate the RMQProducerConnection outside of the new process' memory
    context.

    :param work_queue: process shared queue used to issue work for the
                       producer connection
    """
    producer_connection = RMQProducerConnection(work_queue, log_queue)
    producer_connection.connect()


class RMQProducerConnection(RMQConnection):
    """
    Class RMQProducerConnection

    This class handles a connection to a RabbitMQ server intended for a producer
    entity. Messages to be published are posted to a process shared queue which
    is read continuously by a connection process-local thread assigned to
    monitoring the queue.
    """
    # general
    log_queue: IPCQueue

    # Connection
    _channel = None

    # IPC
    _work_queue: IPCQueue

    def __init__(self, work_queue, log_queue):
        """
        Initializes the RMQProducerConnection's work queue and binds signal
        handlers. The work queue can be used to issue commands.

        :param IPCQueue work_queue: process shared queue used to issue work for
                                    the consumer connection
        :param log_queue: process shared queue used to post messages to the
                          logging process
        """
        self._log_queue = log_queue
        self._log_queue.put(
            LogItem("__init__", RMQProducerConnection.__name__, level=logging.DEBUG)
        )

        self._work_queue = work_queue

        self._channel = RMQProducerChannel(log_queue)

        signal.signal(signal.SIGINT, self.interrupt)
        signal.signal(signal.SIGTERM, self.terminate)

        super().__init__()

    def on_connection_open(self, connection):
        """
        Callback when a connection has been established to the RMQ server.

        :param pika.SelectConnection connection: established connection
        """
        self._log_queue.put(
            LogItem("on_connection_open connection: {}".format(connection),
                    RMQProducerConnection.__name__, level=logging.DEBUG)
        )
        self._channel.open_channel(connection, self.on_channel_open)

    def on_connection_closed(self, _connection, reason):
        loglevel = logging.WARNING if not self._closing else logging.INFO

        self._log_queue.put(
            LogItem("on_connection_closed connection: {} reason: {}"
                    .format(_connection, reason),
                    RMQProducerConnection.__name__, level=loglevel)
        )

        if self._closing:
            self.finalize_disconnect()
        else:
            # TODO: reconnect handling goes here
            self.finalize_disconnect()

    def on_channel_open(self):
        self._log_queue.put(
            LogItem("on_channel_open",
                    RMQProducerConnection.__name__,
                    level=logging.DEBUG)
        )
        self.producer_connection_started()

    def producer_connection_started(self):
        """
        Shall be called when the producer connection has reached a state where
        it is ready to receive and execute work, for instance to publish
        messages.
        """
        self._log_queue.put(
            LogItem("producer_connection_started",
                    RMQProducerConnection.__name__)
        )
        thread = Thread(target=self.monitor_work_queue, daemon=True)
        thread.start()

    def monitor_work_queue(self):
        """
        NOTE!

        This function should live in its own thread so that the
        RMQProducerConnection is able to respond to incoming work as quickly as
        possible.

        Monitors the producer connection's work queue and executes from it as
        soon as work is available.
        """
        self._log_queue.put(
            LogItem("monitor_work_queue", RMQProducerConnection.__name__,
                    level=logging.DEBUG)
        )
        work = self._work_queue.get()
        self._channel.handle_work(work)
        self.monitor_work_queue()

    def interrupt(self, _signum, _frame):
        """
        Signal handler for signal.SIGINT.

        :param int _signum: signal.SIGINT
        :param ??? _frame: current stack frame
        """
        self._log_queue.put(
            LogItem("interrupt", RMQProducerConnection.__name__)
        )
        self.disconnect()

    def terminate(self, _signum, _frame):
        """
        Signal handler for signal.SIGTERM.

        :param int _signum: signal.SIGTERM
        :param ??? _frame: current stack frame
        """
        self._log_queue.put(
            LogItem("terminate", RMQProducerConnection.__name__)
        )
        self.disconnect()
