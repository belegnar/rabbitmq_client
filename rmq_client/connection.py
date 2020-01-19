import pika

from abc import ABCMeta, abstractmethod


class RMQConnection(metaclass=ABCMeta):
    """
    Class RMQConnection

    Abstract class implementing the basics of a RabbitMQ server connection. This
    class does not meddle with channels as the handling of a channel may differ
    between consumers and producers. The RMQConnection class therefore only
    handles the connection (pika.SelectConnection) object itself.

    Subclasses inheriting from RMQConnection have to override the
    on_connection_open(connection: SelectConnection) function to take over once
    the connection has been established. At this point, it is possible to start
    creating channels.
    """

    _connection_parameters: pika.ConnectionParameters
    _connection: pika.SelectConnection

    _closing: bool

    def __init__(self):
        """
        Initializes the RMQ connection with connection parameters and the
        general state of the RMQConnection adapter.
        """
        self._connection_parameters = pika.ConnectionParameters()

        self._connection = pika.SelectConnection(
            parameters=self._connection_parameters,
            on_open_callback=self.on_connection_open,
            on_close_callback=self.on_connection_closed
        )

        self._closing = False

    def connect(self):
        """
        Initiates the connection to the RabbitMQ server by starting the
        connection's IO-loop. Starting the IO-loop will connect to the RabbitMQ
        server as configured in __init__.
        """
        self._connection.ioloop.start()

    @abstractmethod
    def on_connection_open(self, _connection):
        """
        Callback upon opened connection. Subclasses shall override this function
        in order to be notified when a connection has been established in order
        for them to know when they are able to create channels.

        :param pika.SelectConnection _connection: connection that was opened
        """
        pass

    @abstractmethod
    def on_connection_closed(self, _connection, reason):
        """
        Callback upon closed connection. Subclasses shall override this function
        in order to be notified when a connection has been closed.

        :param pika.SelectConnection _connection: connection that was closed
        :param Exception reason: reason for closing
        """
        pass

    def disconnect(self):
        """
        Disconnects from the RabbitMQ server by calling close() on the
        connection object. This operation should result in on_connection_closed
        being invoked once the connection has been closed, allowing for further
        handling of either gracefully shutting down or re-connecting.
        """
        print("closing connection")

        if not self._closing:
            self._closing = True
            self._connection.close()
            return

        print("connection is already closing")

    def finalize_disconnect(self):
        """
        Shall be called once the connection has been closed to stop the IOLoop.
        """
        self._connection.ioloop.stop()
