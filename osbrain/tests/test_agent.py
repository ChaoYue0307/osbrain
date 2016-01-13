import time
import pytest
import random
from threading import Timer
from Pyro4.errors import NamingError
from osbrain.core import locate_ns
from osbrain.core import run_agent
from osbrain.core import Agent
from osbrain.core import Proxy
from osbrain.core import NSProxy
from osbrain.core import NameServer
from osbrain.core import SocketAddress


@pytest.fixture(scope='function')
def nsaddr(request):
    while True:
        try:
            # Bind to random port
            host = '127.0.0.1'
            port = random.randrange(10000, 20000)
            addr = SocketAddress(host, port)
            ns = NameServer(addr)
            def terminate():
                print('addfinalizer...')
                ns.kill()
            request.addfinalizer(terminate)
            ns.start()
            return addr
        except NamingError:
            continue
        except PermissionError:
            continue


def test_nameserver(nsaddr):
    """
    A simple test that checks the correct creation of a name server.
    """
    nsproxy = NSProxy(nsaddr)
    agents = nsproxy.list()
    name = 'Pyro.NameServer'
    assert len(agents) == 1
    assert list(agents.keys())[0] == name
    assert agents[name] == 'PYRO:%s@%s' % (name, nsaddr)


def test_locate_ns():
    """
    Locate nameserver as fast as possible. The function `locate_ns` should
    have a timeout before raising an error.
    """
    while True:
        try:
            # Bind to random port
            host = '127.0.0.1'
            port = random.randrange(10000, 20000)
            addr = SocketAddress(host, port)
            ns = NameServer(addr)
            # Start name server later
            Timer(1, ns.start).start()
            # Locate name server now
            nsaddr = NSProxy(addr).addr()
        except PermissionError:
            continue
        break
    assert nsaddr.host == host
    assert nsaddr.port == port
    ns.kill()


def test_early_agent_proxy(nsaddr):
    """
    It must be possible to create a Proxy when the registration of the new
    agent is imminent, even if it has not occured yet. A timeout will occur
    in case the agent could not be located.
    """
    agent = Agent('a0', nsaddr)
    # Start agent later
    Timer(1, agent.start).start()
    # Locate agent now
    a0 = Proxy('a0', nsaddr)
    assert a0.test() == 'OK'


def test_agent_loopback(nsaddr):
    """
    An agent should always have a loopback inproc socket.
    """
    a0 = run_agent('a0', nsaddr)
    assert a0.get_addr('loopback') == 'inproc://loopback'


def test_ping(nsaddr):
    """
    Test simple loopback ping.
    """
    a0 = run_agent('a0', nsaddr)
    assert a0.ping() == 'PONG'


def test_registration(nsaddr):
    """
    Verify new agents get registered in the nameserver.
    """
    a0 = run_agent('a0', nsaddr)
    a1 = run_agent('a1', nsaddr)
    # List registered agents
    agent_list = NSProxy(nsaddr).list()
    assert 'a0' in agent_list
    assert 'a1' in agent_list


# TODO: this function is used just within the scope of the next test.
#       Could we directly send the bytecode to the agent so that we can
#       declare it within a more constrained scope? (i.e. in the test code).
def rep_handler(agent, message):
    agent.send('reply', 'OK')


def test_reqrep(nsaddr):
    """
    Simple request-reply pattern between two agents.
    """
    a0 = run_agent('a0', nsaddr)
    a1 = run_agent('a1', nsaddr)
    addr = a0.bind('REP', 'reply', rep_handler)
    a1.connect(addr, 'request')
    response = a1.send_recv('request', 'Hello world')
    assert response == 'OK'
