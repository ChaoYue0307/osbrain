"""
Test file for address module.
"""
from collections import namedtuple

import zmq
import pytest

from osbrain.address import address_to_host_port
from osbrain.address import SocketAddress
from osbrain.address import AgentAddress
from osbrain.address import AgentAddressKind
from osbrain.address import AgentAddressRole
from osbrain.address import AgentAddressTransport


def twin_list(elements):
    result = elements[:]
    result[1::2] = elements[::2]
    result[::2] = elements[1::2]
    return result


def test_invalid_address_to_host_port():
    """
    Test conversion of a wrong type to its corresponding host+port tuple.
    This conversion should cause an exception raising.
    """
    with pytest.raises(ValueError):
        address_to_host_port(1.234)


@pytest.mark.parametrize(('address', 'host', 'port'), [
    (None, None, None),
    (AgentAddress('tcp', '127.0.0.1:123', 'PUSH', 'server', 'pickle'), '127.0.0.1', 123),
    (SocketAddress('127.0.0.1', 123), '127.0.0.1', 123),
    ('127.0.0.1:123', '127.0.0.1', 123),
    ('127.0.0.1', '127.0.0.1', None),
    (namedtuple('Foo', ['host', 'port'])('127.0.0.1', 123), '127.0.0.1', 123),
])
def test_valid_address_to_host_port(address, host, port):
    """
    Test conversion of an address to its corresponding host+port tuple.
    """
    assert address_to_host_port(address) == (host, port)


def test_transport():
    """
    This test aims to cover basic AgentAddressTransport initialization and
    equivalence.
    """
    assert AgentAddressTransport('tcp') == 'tcp'
    assert AgentAddressTransport('ipc') == 'ipc'
    assert AgentAddressTransport('inproc') == 'inproc'
    with pytest.raises(ValueError):
        AgentAddressTransport('foo')


def test_kind():
    """
    This test aims to cover basic AgentAddressKind operations: initialization,
    equivalence and basic methods.
    """
    strings = ['REQ', 'REP', 'PUSH', 'PULL', 'PUB', 'SUB']
    zmqints = [zmq.REQ, zmq.REP, zmq.PUSH, zmq.PULL, zmq.PUB, zmq.SUB]
    handlers = [False, True, False, True, False, True]
    strtwins = twin_list(strings)
    zmqtwins = twin_list(zmqints)
    configurations = zip(strings, strtwins, zmqints, zmqtwins, handlers)
    # Make sure there are no missing values
    assert len(list(configurations)) == len(strings)

    for string, strtwin, zmqint, zmqtwin, handler in configurations:
        # Initialization and equivalence
        kind = AgentAddressKind(string)
        assert kind == zmqint
        assert kind == string
        assert kind == AgentAddressKind(zmqint)
        assert kind == AgentAddressKind(kind)
        # Basic methods
        assert isinstance(kind.twin(), AgentAddressKind)
        assert kind.twin() == strtwin
        assert kind.requires_handler() == handler
    # Value error exceptions
    with pytest.raises(ValueError):
        AgentAddressKind('FOO')


def test_role():
    """
    This test aims to cover basic AgentAddressRole operations: initialization,
    equivalence and basic methods.
    """
    values = ['server', 'client']
    twins = twin_list(values)
    for value, twin in zip(values, twins):
        # Initialization and equivalence
        role = AgentAddressRole(value)
        assert role == value
        assert role == AgentAddressRole(role)
        # Basic methods
        assert isinstance(role.twin(), AgentAddressRole)
        assert role.twin() == twin
    # Value error exceptions
    with pytest.raises(ValueError):
        AgentAddressRole('foo')
    with pytest.raises(ValueError):
        AgentAddressRole(1)


def test_socket_address():
    """
    Test basic SocketAddress operations: initialization and equivalence.
    """
    address = SocketAddress('127.0.0.1', 1234)
    # Equivalence
    assert address == SocketAddress('127.0.0.1', 1234)
    assert address != SocketAddress('127.0.0.0', 1234)
    assert address != SocketAddress('127.0.0.1', 1230)
    assert not address == 'foo'
    assert address != 'foo'


def test_agent_address():
    """
    Test basic AgentAddress operations: initialization, equivalence and
    basic methods.
    """
    address = AgentAddress('ipc', 'addr', 'PUSH', 'server')
    # Equivalence
    assert address == AgentAddress('ipc', 'addr', 'PUSH', 'server')
    assert not address == 'foo'
    assert address != 'foo'
    # Basic methods
    assert address.twin() == AgentAddress('ipc', 'addr', 'PULL', 'client')


def test_agent_address_explicit_serializer():
    """
    Test basic AgentAddress operations: initialization, equivalence and
    basic methods when an explicit serializer is used.
    """
    address = AgentAddress('ipc', 'addr', 'PUSH', 'server', 'raw')
    # Equivalence
    assert address == AgentAddress('ipc', 'addr', 'PUSH', 'server', 'raw')
    assert not address == 'foo'
    assert address != 'foo'
    # Basic methods
    assert address.twin() == AgentAddress('ipc', 'addr', 'PULL', 'client',
                                          'raw')
    assert address.twin() != AgentAddress('ipc', 'addr', 'PULL', 'client',
                                          'pickle')


def test_agent_address_to_host_port():
    """
    An agent address should be convertible to host+port if TCP is used.
    """
    address = AgentAddress('tcp', '127.0.0.1:1234', 'PUSH', 'server')
    assert address_to_host_port(address) == ('127.0.0.1', 1234)
