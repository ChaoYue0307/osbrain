************************
Introduction and Example
************************

.. image:: _static/osbrain-logo-name.svg
   :align: center
   :alt: osBrain logo


.. index:: features

About osBrain: feature overview
===============================

osBrain is a **general-purpose multi-agent system module** written in Python.

- Agents run **independently** as system processes and communicate with each
  other using **message passing**.
- Message passing is implemented using `ØMQ <http://zeromq.org/>`_, and in
  particular, the `PyZMQ <https://github.com/zeromq/pyzmq>`_ Python bindings.
- `ØMQ <http://zeromq.org/>`_ allows for **efficient**, **asynchronous**
  communication using different commonly used communication **patterns** such
  as request-reply, push-pull and publish-subscribe.
- osBrain integrates `Pyro4 <https://pythonhosted.org/Pyro4/>`_ to ease the
  configuration and deployment of complex systems.
- Thanks to `Pyro4 <https://pythonhosted.org/Pyro4/>`_, **remote agents can be
  treated as local** objects and reconfigured even when they are running. Not
  just variables, but also new methods can be created in the remote agents.
- osBrain provides the base for implementing robust, highly-available,
  flexible multi-agent systems.
- Being implemented in Python, osBrain can take advantage of a huge set of
  packages for data analysis, statistics, numerical computing, etc. available
  in the Python ecosystem.

In order to fully understand osBrain capabilities, it is **highly recommended**
to read the `Pyro4 documentation <https://pythonhosted.org/Pyro4/>`_ and the
`ØMQ guide <http://zguide.zeromq.org/page:all>`_.


.. index:: history

OsBrain's history
^^^^^^^^^^^^^^^^^

osBrain was initially developed in
`OpenSistemas <http://www.opensistemas.com>`_ based on the need to create a
**real-time automated-trading platform**. This platform needed to be able to
process real-time market data updates fast and in a parallel way. Robustness
was very important as well in order to prevent running trading strategies
from being affected by a failure in another strategy.

Python was chosen for being a great language for fast prototyping and for
having a huge data analysis ecosystem available. It was kept for its final
performance and the beautiful source code created with it.

The appearance of osBrain was a consecuence of a series of steps that were
taken during the development process:

#. **Isolation of agents**; creating separate system processes to avoid shared
   memory and any problems derived from multi-threading development.
#. **Implementation of message passing**; making use of the modern, efficient
   and flexible `ØMQ <http://zeromq.org/>`_ library.
#. **Ease of configuration/deployment**; making use of the very convenient,
   well implemented and documented `Pyro4 <https://pythonhosted.org/Pyro4/>`_
   package.
#. **Separation from the trading platform**; what it started as a basic
   architecture to implement a real-time automated-trading platform, ended-up
   being a general-purpose multi-agent system architecture.


.. index:: usage

What can you use osBrain for?
=============================

osBrain has been successfully used to develop a real-time automated-trading
platform in `OpenSistemas <http://www.opensistemas.com>`_, but being a
general-purpose multi-agent system, it is not limited to this application.
Other applications include:

- Transportation.
- Logistics.
- Defense and military applications.
- Networking.
- Load balancing.
- Self-healing networks.

In general, osBrain can be used whenever a multi-agent system architecture
fits the application well:

- Autonomy of the agents.
- Local views.
- Decentralization.


.. index:: example

Simple Example
==============

In the following example we run a very simple architecture in three steps:

#. Run a name server, which will register agents running by their alias.
#. Run an agent with an alias ``Example``.
#. Log a ``Hello world`` message from the agent.

.. literalinclude:: ../../examples/hello_world.py

It is important to note that the ``agent`` variable in that example is just
what is called a proxy to the remote agent so, when ``log_info()`` is called,
this method is actually serialized and executed in the remote agent. Remember
that the agent is running as a separate system process!


.. index:: performance

Performance
===========

The performance of osBrain, just as the performance of any other system
architecture, depends a lot on the actual application. The developer should
always take this into account:

#. Pyro4 is used only for configuration and deployment, which means that
   the actual performance of the system does not depend on this package.
#. `ØMQ <http://zeromq.org/>`_ is used with the
   `PyZMQ <https://github.com/zeromq/pyzmq>`_ Python bindings, which means
   that the system performance depends on the
   `PyZMQ <https://github.com/zeromq/pyzmq>`_ performance.
#. osBrain uses `pickle <https://docs.python.org/library/pickle.html>`_ for
   serialization, which means that the system performance depends on this
   package.
#. ØMQ transport is TCP by default. The network may have a great impact on
   performance.
