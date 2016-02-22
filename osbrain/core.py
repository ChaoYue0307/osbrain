"""
Core agent classes.
"""
import types
import signal
import sys
import time
import inspect
import multiprocessing
import pickle
import errno
import zmq
import Pyro4
from Pyro4.errors import PyroError
from Pyro4.errors import NamingError
from .common import address_to_host_port
from .common import unbound_method
from .common import LogLevel
from .address import AgentAddress
from .address import AgentAddressKind
from .proxy import Proxy
from .proxy import NSProxy


Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.THREADPOOL_SIZE = 16
Pyro4.config.SERVERTYPE = 'multiplex'
# TODO: should we set COMMTIMEOUT as well?


class BaseAgent():
    def __init__(self, name=None, host=None):
        # Set name
        self.name = name

        # The `socket` key is the address or the alias; value is the socket
        self.socket = {}
        # The `address` key is the alias; value is the address
        self.address = {}
        # The `handler` key is the socket
        self.handler = {}
        # Polling timeout
        self.poll_timeout = 1000
        # Keep alive
        self.keep_alive = True
        # Kill parent agent process
        self.kill_agent = False
        # Agent running
        self.running = False
        # Defaut host
        self.host = host
        if not self.host:
            self.host = '127.0.0.1'

        try:
            self.context = zmq.Context()
            self.poller = zmq.Poller()
        except zmq.ZMQError as error:
            self.log_error('Initialization failed: %s' % error)
            raise
        # This in-process socket could, eventually, handle safe access to
        # memory from other threads (i.e. when using Pyro proxies).
        socket = self.context.socket(zmq.REP)
        address = 'inproc://loopback'
        socket.bind(address)
        self.register(socket, address, 'loopback', self.handle_loopback)

        self.on_init()

    def on_init(self):
        pass

    # TODO: __getitem__ could select sockets by name (i.e. Agent()['rep0'])
    def __getitem__(self, key):
        pass

    def handle_loopback(self, message):
        header, data = message
        if header == 'PING':
            return 'PONG'
        if header == 'STOP':
            self.log_info('Stopping...')
            self.keep_alive = False
            return 'OK'
        if header == 'CLOSE':
            self.log_info('Closing sockets...')
            self.close_sockets()
            return 'OK'
        self.log_error('Unrecognized message: %s %s' % (header, data))

    def loopback(self, header, data=None):
        if not self.running:
            raise NotImplementedError()
        loopback = self.context.socket(zmq.REQ)
        loopback.connect('inproc://loopback')
        loopback.send_pyobj((header, data))
        return loopback.recv_pyobj()

    def ping(self):
        return self.loopback('PING')

    def stop(self):
        return self.loopback('STOP')

    def _log_message(self, level, message, logger='log'):
        level = LogLevel(level)
        message = '(%s): %s' % (self.name, message)
        if self.registered(logger):
            logger_kind = AgentAddressKind(self.socket[logger].socket_type)
            assert logger_kind == 'PUB', \
                'Logger must use publisher-subscriber pattern!'
            self.send(logger, message, topic=level)
        elif level == 'INFO':
            sys.stdout.write('INFO %s\n' % message)
            sys.stdout.flush()
        # When logging an error, always write to stderr
        if level == 'ERROR':
            sys.stderr.write('ERROR %s\n' % message)
            sys.stderr.flush()
        # When logging a warning, always write to stdout
        elif level == 'WARNING':
            sys.stdout.write('WARNING %s\n' % message)
            sys.stdout.flush()

    def log_error(self, message, logger='log'):
        self._log_message('ERROR', message, logger)

    def log_warning(self, message, logger='log'):
        self._log_message('WARNING', message, logger)

    def log_info(self, message, logger='log'):
        self._log_message('INFO', message, logger)

    def addr(self, alias):
        return self.address[alias]

    def get_addr(self, alias):
        # TODO: deprecate
        self.log_warning('get_addr() is deprecated! use addr() instead')
        return self.addr(alias)

    def register(self, socket, address, alias=None, handler=None):
        assert not self.registered(address), \
            'Socket is already registered!'
        if not alias:
            alias = address
        self.socket[alias] = socket
        self.socket[address] = socket
        self.address[alias] = address
        if handler is not None:
            try:
                self.poller.register(socket, zmq.POLLIN)
            except zmq.ZMQError as error:
                self.log_error('Error registering socket: %s' % error)
                raise
            self.set_handler(socket, handler)

    def set_handler(self, socket, handler):
        # TODO: clean-up
        if isinstance(handler, types.FunctionType):
            self.handler[socket] = handler
            return
        if isinstance(handler, types.MethodType):
            self.handler[socket] = unbound_method(handler)
            return
        if isinstance(handler, list):
            handlers = []
            for h in handler:
                if isinstance(h, types.FunctionType):
                    handlers.append(h)
                elif isinstance(h, types.MethodType):
                    handlers.append(unbound_method(h))
            self.handler[socket] = handlers
            return
        if isinstance(handler, dict):
            handlers = {}
            for key in handler:
                if isinstance(handler[key], types.FunctionType):
                    handlers[key] = handler[key]
                elif isinstance(handler[key], types.MethodType):
                    handlers[key] = unbound_method(handler[key])
            self.handler[socket] = handlers
            return
        # TODO: allow `str` (method name)
        raise NotImplementedError('Only functions/methods are allowed!')

    def registered(self, address):
        return address in self.socket

    def bind(self, kind, alias=None, handler=None, host=None, port=None):
        kind = AgentAddressKind(kind)
        assert not kind.requires_handler() or handler is not None, \
            'This socket requires a handler!'
        if not host:
            host = self.host
        try:
            socket = self.context.socket(kind)
            if not port:
                uri = 'tcp://%s' % host
                port = socket.bind_to_random_port(uri)
            else:
                socket.bind('tcp://%s:%s' % (host, port))
        except zmq.ZMQError as error:
            self.log_error('Socket creation failed: %s' % error)
            raise
        server_address = AgentAddress(host, port, kind, 'server')
        self.register(socket, server_address, alias, handler)
        # SUB sockets are a special case
        if kind == 'SUB':
            self.subscribe(server_address, handler)
        return server_address

    def connect(self, server_address, alias=None, handler=None):
        assert server_address.role == 'server', \
            'Incorrect address! A server address must be provided!'
        client_address = server_address.twin()
        assert not client_address.kind.requires_handler() or \
            handler is not None, 'This socket requires a handler!'
        if self.registered(client_address):
            self._connect_old(client_address, alias, handler)
        else:
            self._connect_new(client_address, alias, handler)

    def _connect_old(self, client_address, alias=None, handler=None):
        assert handler is None, \
            'Undefined behavior when a new handler is given! (TODO)'
        self.socket[alias] = self.socket[client_address]
        self.address[alias] = client_address
        return client_address

    def _connect_new(self, client_address, alias=None, handler=None):
        try:
            # TODO: when using `socket(str(client_address.kind))` and running
            #       (for example) examples/push_pull/, we get a TypeError
            #       (integer is required). However, the line is not displayed.
            #       Perhaps we could improve the traceback display?
            socket = self.context.socket(client_address.kind)
            socket.connect('tcp://%s:%s' % (client_address.host,
                                            client_address.port))
        except zmq.ZMQError as error:
            self.log_error('Could not connect: %s' % error)
            raise
        self.register(socket, client_address, alias, handler)
        return client_address

    def subscribe(self, alias, handlers):
        """
        TODO
        """
        if not isinstance(handlers, dict):
            handlers = {'': handlers}
        for topic in handlers.keys():
            assert isinstance(topic, str), 'Topic must be of type `str`!'
            topic = self.str2bytes(topic)
            self.socket[alias].setsockopt(zmq.SUBSCRIBE, topic)
        # Reset handlers
        self.set_handler(self.socket[alias], handlers)

    def iddle(self):
        """
        This function is to be executed when the agent is iddle.

        After a timeout occurs when the agent's poller receives no data in
        any of its sockets, the agent may execute this function.

        Note
        ----
        The timeout is set by the agent's `poll_timeout` attribute.
        """
        pass

    def set_attr(self, **kwargs):
        for name, value in kwargs.items():
            setattr(self, name, value)

    def get_attr(self, name):
        return getattr(self, name)

    def new_method(self, method, name=None):
        method = types.MethodType(method, self)
        if not name:
            name = method.__name__
        setattr(self, name, method)

    # TODO: remove/deprecate. If an Agent is to be active, then loopback could
    #       be used to send execution orders. E.g.: each second, send function
    #       over loopback and let it be executed by the main thread.
    def set_loop(self, loop):
        self.loop = types.MethodType(loop, self)

    def execute(self, function, *args, **kwargs):
        return function(args, kwargs)

    def self_execute(self, function, *args, **kwargs):
        if args and kwargs:
            return function(self, args, kwargs)
        if args:
            return function(self, args)
        if kwargs:
            return function(self, kwargs)
        return function(self)

    def loop(self):
        """
        Agent's main loop.

        This loop is executed until the `keep_alive` attribute is False
        or until an error occurs.
        """
        while self.keep_alive:
            if self.iterate():
                break

    def graceful_end(self):
        """
        Agent graceful termination. It ends current loop of work before exiting.
        """
        # TODO: deprecate
        self.log_warning('graceful_end() is deprecated! use stop() instead')
        self.keep_alive = False

    def iterate(self):
        """
        Agent's main iteration.

        This iteration is normally executed inside the main loop.

        The agent is polling all its sockets for input data. It will wait
        for `poll_timeout`; after this period, the method `iddle` will be
        executed before polling again.

        Returns
        -------
        int
            1 if an error occurred during the iteration (we would expect this
            to happen if an interruption occurs during polling).

            0 otherwise.
        """
        try:
            events = dict(self.poller.poll(self.poll_timeout))
        except zmq.ZMQError as error:
            # Raise the exception in case it is not due to SIGINT
            if error.errno != errno.EINTR:
                raise
            else:
                return 1

        if not events:
            # Agent is iddle
            self.iddle()
            return 0

        for socket in events:
            if events[socket] != zmq.POLLIN:
                continue
            serialized = socket.recv()
            socket_kind = AgentAddressKind(socket.socket_type)
            if socket_kind == 'SUB':
                handlers = self.handler[socket]
                sepp = serialized.index(b'\x80')
                topic = serialized[:sepp]
                data = serialized[sepp:]
                try:
                    message = pickle.loads(data)
                except ValueError:
                    error = 'Could not load pickle stream! %s' % data
                    self.log_error(error)
                    continue
                for str_topic in handlers:
                    btopic = self.str2bytes(str_topic)
                    if not serialized.startswith(btopic):
                        continue
                    # Call the handler (with or without the topic)
                    handler = handlers[str_topic]
                    nparams = len(inspect.signature(handler).parameters)
                    if nparams == 2:
                        handler(self, message)
                    elif nparams == 3:
                        handler(self, message, topic)
            else:
                message = pickle.loads(serialized)
                handlers = self.handler[socket]
                if not isinstance(handlers, list):
                    handlers = [handlers]
                # TODO: test (allow multiple handlers, which get executed in
                #       order)
                for handler in handlers:
                    handler_return = handler(self, message)
            if socket_kind == 'REP':
                if handler_return is not None:
                    socket.send_pyobj(handler_return)

        return 0

    def str2bytes(self, message):
        # TODO: what happens if the topic is non-ASCII?
        return message.encode('ascii')

    def send(self, address, message, topic=''):
        assert isinstance(topic, str), 'Topic must be of `str` type!'
        serialized = pickle.dumps(message, -1)
        topic = self.str2bytes(topic)
        self.socket[address].send(topic + serialized)

    def recv(self, address):
        serialized = self.socket[address].recv()
        deserialized = pickle.loads(serialized)
        return deserialized

    def send_recv(self, address, message):
        self.send(address, message)
        return self.recv(address)

    @Pyro4.oneway
    def run(self):
        """
        Run the agent.
        """
        self.running = True
        self.loop()
        self.running = False

    def stop(self):
        self.loopback('STOP')

    def shutdown(self):
        # Stop the running thread
        if self.running:
            self.loopback('STOP')
        while self.running:
            time.sleep(0.1)
        # Kill the agent
        self.kill()

    def kill(self):
        self.context.destroy()
        self.kill_agent = True

    def close_sockets(self):
        for address in self.socket:
            if address in ('loopback', 'inproc://loopback'):
                continue
            self.socket[address].close()

    def test(self):
        """
        A test method to check the readiness of the agent. Used for testing
        purposes, where timing is very important. Do not remove.
        """
        return 'OK'


class Agent(multiprocessing.Process):
    def __init__(self, name, nsaddr=None, addr=None, base=BaseAgent):
        super().__init__()
        self.name = name
        self.daemon = None
        self.host, self.port = address_to_host_port(addr)
        # TODO: pull request?
        if self.port is None:
            self.port = 0
        self.nsaddr = nsaddr
        self.base = base
        self.shutdown_event = multiprocessing.Event()
        self.permission_error = multiprocessing.Event()
        self.unknown_error = multiprocessing.Event()
        self.os_error = multiprocessing.Event()
        self.daemon_started = multiprocessing.Event()

    def run(self):
        # Capture SIGINT
        signal.signal(signal.SIGINT, self.sigint_handler)

        try:
            ns = NSProxy(self.nsaddr)
        except PyroError as error:
            print(error)
            print('Agent %s is being killed' % self.name)
            return

        try:
            # TODO: infer `host` if is `None` and we are connected to `ns_host`
            #       through a LAN.
            self.daemon = Pyro4.Daemon(self.host, self.port)
        except PermissionError:
            self.permission_error.set()
            return
        except OSError:
            self.os_error.set()
            return
        except:
            self.unknown_error.set()
            raise
        self.daemon_started.set()

        self.agent = self.base(name=self.name, host=self.host)
        uri = self.daemon.register(self.agent)
        ns.register(self.name, uri)
        ns._pyroRelease()

        print('%s ready!' % self.name)
        self.daemon.requestLoop(lambda: not self.shutdown_event.is_set() and
                                        not self.agent.kill_agent)
        try:
            ns = NSProxy(self.nsaddr)
            ns.remove(self.name)
        except PyroError as error:
            print(error)
            print('Agent %s is being killed' % self.name)
            return
        self.agent._killed = True
        self.daemon.close()

    def start(self):
        super().start()
        # TODO: instead of Event(), use message passing to handle exceptions.
        #       It would be easier to know the exact exception that occurred.
        while not self.daemon_started.is_set() and \
              not self.permission_error.is_set() and \
              not self.os_error.is_set() and \
              not self.unknown_error.is_set():
            time.sleep(0.01)
        if self.unknown_error.is_set():
            raise RuntimeError('Unknown error occured while creating daemon!')
        elif self.os_error.is_set():
            raise OSError('TODO: use message passing to know the exact error')
        elif self.permission_error.is_set():
            self.permission_error.clear()
            raise PermissionError()

    def kill(self):
        self.shutdown_event.set()
        if self.daemon:
            self.daemon.shutdown()

    def sigint_handler(self, signal, frame):
        """
        Handle interruption signals.
        """
        self.kill()


def run_agent(name, nsaddr=None, addr=None, base=BaseAgent):
    """
    Ease the agent creation process.

    This function will create a new agent, start the process and then run
    its main loop through a proxy.

    Parameters
    ----------
    name : str
        Agent name or alias.
    nsaddr : SocketAddress, default is None
        Name server address.
    addr : SocketAddress, default is None
        New agent address, if it is to be fixed.

    Returns
    -------
    proxy
        A proxy to the new agent.
    """
    Agent(name, nsaddr=nsaddr, addr=addr, base=base).start()
    proxy = Proxy(name, nsaddr)
    proxy.run()
    return proxy
