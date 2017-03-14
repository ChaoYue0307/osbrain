"""
Proxy module tests.
"""
import os
import time

import pytest

from osbrain import run_agent
from osbrain import Agent
from osbrain import Proxy
from osbrain import NSProxy
from osbrain.proxy import locate_ns

from common import nsproxy  # pragma: no flakes


def since(t0, passed, tolerance):
    return abs((time.time() - t0) - passed) < tolerance


class DelayAgent(Agent):
    def delay(self, seconds):
        time.sleep(seconds)


class BussyWorker(Agent):
    def on_init(self):
        self.bind('PULL', alias='pull', handler=self.stay_bussy)
        self.bussy = False

    def stay_bussy(self, delay):
        self.bussy = True
        time.sleep(delay)
        self.bussy = False

    def listen(self):
        return 'OK'


def setup_bussy_worker(nsproxy):
    worker = run_agent('worker', base=BussyWorker)
    boss = run_agent('boss')
    boss.connect(worker.addr('pull'), alias='push')
    # Make worker bussy for 2 seconds
    boss.send('push', 2)
    while not worker.get_attr('bussy'):
        time.sleep(0.01)
    return worker


def time_threads(threads):
    """
    Start all threads in a given list and wait for all of them to finish.

    Parameters
    ----------
    threads : list(Thread)
        A list containing all the threads.

    Returns
    -------
    float
        The number of seconds that took all threads to finish their jobs.
    """
    t0 = time.time()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return time.time() - t0


def test_wrong_nameserver_address():
    """
    Locating a name server that does not exist should raise an error.
    """
    with pytest.raises(TimeoutError):
        locate_ns('127.0.0.1:22', timeout=1.)


def test_proxy_without_nsaddr(nsproxy):
    """
    Creating a proxy without specifying the name server address should
    result in the OSBRAIN_NAMESERVER_ADDRESS being used.
    """
    agent0 = run_agent('foo')
    agent0.set_attr(x=1.)
    agent1 = Proxy('foo')
    assert agent1.get_attr('x') == 1.


def test_agent_proxy_remote_exceptions(nsproxy):
    """
    Remote exceptions on method executions should be raised locally by the
    proxy with information on what did go wrong remotely.
    """
    a0 = run_agent('a0')
    a1 = run_agent('a1')
    with pytest.raises(TypeError) as error:
        a0.addr('asdf', 'qwer', 'foo', 'bar')
    assert 'positional arguments but 5 were given' in str(error.value)
    with pytest.raises(RuntimeError) as error:
        a1.raise_exception()
    assert 'User raised an exception' in str(error.value)


def test_agent_proxy_initialization_timeout(nsproxy):
    """
    An agent proxy should raise a TimeoutError at initialization if the agent
    is not ready after a number of seconds.
    """
    class InitTimeoutProxy(Proxy):
        def ready(self):
            time.sleep(0.1)
            raise TimeoutError()

    run_agent('foo')
    with pytest.raises(TimeoutError):
        InitTimeoutProxy('foo', timeout=1.)


def test_nameserver_proxy_shutdown_timeout(nsproxy):
    """
    A NSProxy should raise a TimeoutError if all agents were not shutted
    down and unregistered after a number of seconds.
    """
    class ShutdownTimeoutNSProxy(NSProxy):
        def agents(self):
            return ['agent_foo']

    timeoutproxy = ShutdownTimeoutNSProxy(nsproxy.addr())
    with pytest.raises(TimeoutError):
        timeoutproxy.shutdown(timeout=1.)


def test_agent_proxy_nameserver_address(nsproxy):
    """
    Agent proxies should be able to return the name server address.
    """
    agent = run_agent('foo')
    assert agent.nsaddr() == nsproxy.addr()


def test_agent_proxy_safe_and_unsafe_property(nsproxy):
    """
    Using the safe/unsafe property from a proxy should allow us to
    override the environment global configuration.
    """
    run_agent('foo', base=DelayAgent)
    # Safe environment
    os.environ['OSBRAIN_DEFAULT_SAFE'] = 'true'
    proxy = Proxy('foo')
    assert proxy._safe
    assert proxy.safe._safe
    assert not proxy.unsafe._safe
    # Unsafe environment
    os.environ['OSBRAIN_DEFAULT_SAFE'] = 'false'
    proxy = Proxy('foo')
    assert not proxy._safe
    assert proxy.safe._safe
    assert not proxy.unsafe._safe


def test_agent_proxy_safe_and_unsafe_parameter(nsproxy):
    """
    Using the safe/unsafe parameter when initializating a proxy should allow
    us to override the environment global configuration.
    """
    run_agent('foo', base=DelayAgent)
    # Safe environment
    os.environ['OSBRAIN_DEFAULT_SAFE'] = 'true'
    proxy = Proxy('foo')
    assert proxy._safe
    proxy = Proxy('foo', safe=False)
    assert not proxy._safe
    # Unsafe environment
    os.environ['OSBRAIN_DEFAULT_SAFE'] = 'false'
    proxy = Proxy('foo')
    assert not proxy._safe
    proxy = Proxy('foo', safe=True)
    assert proxy._safe


def test_agent_proxy_safe_and_unsafe_calls_property_safe(nsproxy):
    """
    An agent can be accessed through a proxy in both safe and unsafe ways.
    When using the `safe` property, calls are expected to wait until the main
    thread is able to process them to avoid concurrency.
    """
    os.environ['OSBRAIN_DEFAULT_SAFE'] = 'false'
    worker = setup_bussy_worker(nsproxy)
    assert not worker._safe
    t0 = time.time()
    assert worker.safe.listen() == 'OK'
    assert since(t0, passed=2., tolerance=0.1)
    assert not worker.get_attr('bussy')
    # Calling a method with `.safe` should not change default behavior
    assert not worker._safe


def test_agent_proxy_safe_and_unsafe_calls_property_unsafe(nsproxy):
    """
    An agent can be accessed through a proxy in both safe and unsafe ways.
    When using the `unsafe` property, calls are not expected to wait until
    the main thread is able to process them (concurrency is allowed).
    """
    os.environ['OSBRAIN_DEFAULT_SAFE'] = 'true'
    worker = setup_bussy_worker(nsproxy)
    assert worker._safe
    t0 = time.time()
    assert worker.unsafe.listen() == 'OK'
    assert since(t0, passed=0., tolerance=0.1)
    while worker.get_attr('bussy'):
        time.sleep(0.01)
    assert since(t0, passed=2., tolerance=0.1)
    # Calling a method with `.unsafe` should not change default behavior
    assert worker._safe


def test_agent_proxy_safe_and_unsafe_calls_environ_safe(nsproxy):
    """
    An agent can be accessed through a proxy in both safe and unsafe ways.
    When using the `safe` property, calls are expected to wait until the main
    thread is able to process them to avoid concurrency.
    """
    os.environ['OSBRAIN_DEFAULT_SAFE'] = 'true'
    worker = setup_bussy_worker(nsproxy)
    t0 = time.time()
    assert worker.listen() == 'OK'
    assert since(t0, passed=2., tolerance=0.1)
    assert not worker.get_attr('bussy')


def test_agent_proxy_safe_and_unsafe_calls_environ_unsafe(nsproxy):
    """
    An agent can be accessed through a proxy in both safe and unsafe ways.
    When using the `unsafe` property, calls are not expected to wait until
    the main thread is able to process them (concurrency is allowed).
    """
    os.environ['OSBRAIN_DEFAULT_SAFE'] = 'false'
    worker = setup_bussy_worker(nsproxy)
    t0 = time.time()
    assert worker.listen() == 'OK'
    assert since(t0, passed=0., tolerance=0.1)
    while worker.get_attr('bussy'):
        time.sleep(0.01)
    assert since(t0, passed=2., tolerance=0.1)
