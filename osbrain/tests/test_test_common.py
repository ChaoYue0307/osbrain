"""
Test file for functionality implemented in `osbrain/tests/common.py`.
"""
import pytest

from osbrain import run_agent
from osbrain import run_logger
from osbrain import Agent

from common import nsproxy  # pragma: no flakes
from common import logger_received
from common import sync_agent_logger
from common import agent_dies
from common import attribute_match
from common import wait_agent_attr


def test_agent_dies(nsproxy):
    """
    The function `agent_dies` should return `False` if the agent does not die
    after a timeout.
    """
    run_agent('a0')
    assert not agent_dies('a0', nsproxy, timeout=0.5)


def test_sync_agent_logger(nsproxy):
    """
    After synchronizing and agent and a logger, a message logged should
    always be received by the logger.
    """
    a0 = run_agent('a0')
    logger = run_logger('logger')
    a0.set_logger(logger)
    sync_agent_logger(agent=a0, logger=logger)
    a0.log_info('asdf')
    assert logger_received(logger, 'log_history_info', message='asdf')


def test_logger_received(nsproxy):
    """
    The function `logger_received` should return `False` if the message is
    not received after a timeout.
    """
    a0 = run_agent('a0')
    logger = run_logger('logger')
    a0.set_logger(logger)
    sync_agent_logger(agent=a0, logger=logger)
    assert not logger_received(logger, 'log_history_error', message='asdf')


@pytest.mark.parametrize('attribute,length,data,value,match', [
    ([], 1, None, None, False),
    ([], None, 1, None, False),
    ([], None, None, [], True),
    ({'foo'}, 1, None, None, True),
    ({'foo'}, None, 'foo', None, True),
    ({'foo'}, None, None, {'foo'}, True),
    (42, None, None, 14, False),
    (42, None, None, 42, True),
])
def test_attribute_match(attribute, length, data, value, match):
    """
    Test `attribute_match` function.
    """
    result = attribute_match(attribute, length=length, data=data, value=value)
    assert result == match


def test_wait_agent_attr(nsproxy):
    """
    Test `wait_agent_attr` function.
    """
    class Client(Agent):
        def set_received(self, value):
            self.received = value

    a0 = run_agent('a0', base=Client)

    # Named attribute, zero timeout
    a0.set_attr(x=[])
    assert not wait_agent_attr(a0, 'x', length=1, timeout=0.)

    # Default attribute, timeout
    a0.set_attr(received=0)
    a0.after(1, 'set_received', 42)
    assert not wait_agent_attr(a0, value=42, timeout=0.)
    assert wait_agent_attr(a0, value=42, timeout=2.)
