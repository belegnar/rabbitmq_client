import signal
import functools

from threading import Thread
from multiprocessing import Queue as IPCQueue

from .connection import RMQConnection


def create_producer_connection(work_queue):
    """
    Interface function to instantiate and connect a producer connection. This
    function is intended as a target for a new process to avoid having to
    instantiate the RMQProducerConnection outside of the new process' memory
    context.

    :param work_queue: process shared queue used to issue work for the
                       producer connection
    """
    producer_connection = RMQProducerConnection(work_queue)
    producer_connection.connect()


class RMQProducerConnection(RMQConnection):

    _channel = None

    _work_queue: IPCQueue

    def __init__(self, work_queue):
        """
        Initializes the RMQProducerConnection's work queue and binds signal
        handlers. The work queue can be used to issue commands.

        :param work_queue: process shared queue used to issue work for the
                         consumer connection
        """
        print("producer connection __init__")
        self._work_queue = work_queue

        signal.signal(signal.SIGINT, self.interrupt)
        signal.signal(signal.SIGTERM, self.terminate)

        super().__init__()

    def on_connection_open(self, _connection):
        """
        Callback when a connection has been established to the RMQ server.

        :param _connection: established connection
        """
        print("producer connection open")
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        print("producer connection channel open")
        self._channel = channel
        self._channel.add_on_close_callback(self.on_channel_closed)

        self.producer_connection_started()

    def on_channel_closed(self, channel, reason):
        print("producer connection channel {} closed for reason: {}".format(channel, reason))

    def producer_connection_started(self):
        print("producer connection started")
        thread = Thread(target=self.monitor_work_queue, daemon=True)
        thread.start()

    def monitor_work_queue(self):
        print("producer connection monitoring work queue")
        work = self._work_queue.get()
        self.handle_work(work)
        self.monitor_work_queue()

    def handle_work(self, work):
        print("producer connection got work: {}".format(work))

    def interrupt(self, _signum, _frame):
        """
        Signal handler for signal.SIGINT

        :param _signum: signal.SIGINT
        :param _frame: current stack frame
        :return: None
        """
        print("producer connection interrupt")
        self._closing = True
        self.disconnect()

    def terminate(self, _signum, _frame):
        """
        Signal handler for signal.SIGTERM

        :param _signum: signal.SIGTERM
        :param _frame: current stack frame
        :return: None
        """
        print("producer connection terminate")
        self._closing = True
        self.disconnect()