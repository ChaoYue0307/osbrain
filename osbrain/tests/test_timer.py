"""
Test file for timers.
"""
import time
import pytest
from osbrain.core import Agent
from osbrain.core import run_agent
from osbrain.common import repeat

from common import nsaddr  # pragma: no flakes


def set_received(agent, message, topic=None):
    agent.received = message


@pytest.mark.timeout(1)
def test_repeat_non_blocking():
    """
    A repeated action (i.e. timer) should always be executed in a separate
    thread, even the first execution.
    """
    def foo(x):
        time.sleep(x)

    timer = repeat(1., foo, 2.)
    timer.close()


def test_repeat_close():
    """
    Test closing a timer returned by repeat.
    """
    class Bar():
        def __init__(self):
            self.a = 0

        def foo(self):
            self.a += 1

    bar = Bar()
    timer = repeat(0.1, bar.foo)
    time.sleep(1.)
    assert abs(bar.a - 10) <= 1
    timer.close()
    time.sleep(1.)
    assert abs(bar.a - 10) <= 1


def test_timer_non_blocking_bug(nsaddr):
    """
    A timer call should never block, no matters how long it takes to execute
    the action.
    """
    def long_action(agent):
        time.sleep(1.)
        agent.count += 1

    agent = run_agent('agent')
    agent.set_attr(count=0)
    # Start timer
    t0 = time.time()
    agent.each(0., long_action)
    t1 = time.time()
    assert t1 - t0 < 0.1
    assert agent.get_attr('count') == 0
    time.sleep(1.5)
    assert agent.get_attr('count') > 0


def test_timer_each(nsaddr):
    """
    Test a timer executed periodically.
    """
    def tick(agent):
        agent.send('push', agent.count)
        agent.count += 1

    sender = run_agent('sender')
    sender.set_attr(count=0)
    receiver = run_agent('receiver')
    addr = sender.bind('PUSH', alias='push')
    receiver.connect(addr, handler=set_received)
    # Start timer
    sender.each(0.1, tick)
    time.sleep(2)
    assert abs(receiver.get_attr('received') - 20) <= 1


def test_timer_each_oop(nsaddr):
    """
    Test a timer executed periodically (using OOP).
    """
    class Sender(Agent):
        def on_init(self):
            self.count = 0
            self.bind('PUSH', 'push')

        def tick(self):
            self.send('push', self.count)
            self.count += 1

    sender = run_agent('sender', base=Sender)
    receiver = run_agent('receiver')
    receiver.connect(sender.addr('push'), handler=set_received)
    # Start timer
    sender.each(0.1, 'tick')
    time.sleep(2)
    assert abs(receiver.get_attr('received') - 20) <= 1


def test_timer_each_fall_behind(nsaddr):
    """
    Test a timer executed periodically and falling behind the period.

    If a sequence of events takes longer to run than the time available
    before the next event, the repeater will simply fall behind.
    """
    def tick(agent):
        agent.send('push', agent.count)
        time.sleep(.2)
        agent.count += 1

    sender = run_agent('sender')
    sender.set_attr(count=0)
    receiver = run_agent('receiver')
    addr = sender.bind('PUSH', alias='push')
    receiver.connect(addr, handler=set_received)
    # Start timer
    sender.each(0., tick)
    time.sleep(2.0)
    assert abs(receiver.get_attr('received') - 10) <= 1
