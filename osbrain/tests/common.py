import pytest
from osbrain import run_nameserver


@pytest.fixture(scope='function')
def nsaddr(request):
    ns = run_nameserver()
    yield ns.addr()
    ns.shutdown()


@pytest.fixture(scope='function')
def nsproxy(request):
    ns = run_nameserver()
    yield ns
    ns.shutdown()
