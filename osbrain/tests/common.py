import time
from uuid import uuid4

import pytest
from osbrain import run_nameserver


def logger_received(logger, log_name, message, timeout=1.):
    """
    Check if a logger receives a message.

    Parameters
    ----------
    logger : Proxy
        Proxy to the logger.
    log_name : str
        The name of the attribue to look for in the logger.
    message : anything
        Message to look for in the log. Can be a partial match.
    timeout : float
        After this number of seconds the function will return `False`.

    Returns
    -------
    bool
        Whether the logger received the message or not.
    """
    t0 = time.time()
    while True:
        time.sleep(0.01)
        log_history = logger.get_attr(log_name)
        if len(log_history) and message in log_history[-1]:
            break
        if timeout and time.time() - t0 > timeout:
            return False
    return True


def sync_agent_logger(agent, logger):
    """
    Make sure and agent and a logger are synchronized.

    An agent is synchronized with its logger when we make sure the logger has
    started receiving messages from the agent.

    Parameters
    ----------
    agent : Proxy
        Proxy to the agent.
    logger : Proxy
        Proxy to the logger.
    """
    while not len(logger.get_attr('log_history_info')):
        message = str(uuid4())
        agent.log_info(message)
        time.sleep(0.01)
    while message not in logger.get_attr('log_history_info')[-1]:
        time.sleep(0.01)


def agent_dies(agent, nsproxy, timeout=1.):
    """
    Check if an agent dies within a given period.

    Parameters
    ----------
    agent : str
        Name of the agent, as registered in the name server.
    nsproxy : NSProxy
        Proxy to the name server.
    timeout : float
        After this number of seconds the function will return `False`.

    Returns
    -------
    bool
        Whether the agent died (was unregistered from the name server) within
        the given period.
    """
    t0 = time.time()
    while True:
        time.sleep(0.01)
        if agent not in nsproxy.agents():
            break
        if timeout and time.time() - t0 > timeout:
            return False
    return True


@pytest.fixture(scope='function')
def nsproxy(request):
    ns = run_nameserver()
    yield ns
    ns.shutdown()
