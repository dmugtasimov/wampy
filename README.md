# wampy

## An experimental (and incomplete) WAMP Implementation.

The WAMP protocol connects Clients over RPC or pub/sub via a Router. A Client is some kind of application, maybe a *Caller*, maybe a *Callee*, else a *Publisher* or a *Subscriber*. A *Router* is another type of application - a message broker - and highly likely to be Crossbar.

Whatever application you're dealing with, WAMP refers to these as a __Peer__.

With __wampy__ you can create Peers to implement WAMP roles: Callee, Caller, Publisher, Subscriber, Broker and Dealer.

### Quickstart: wampy from a Python console.

Before any messaging can happen you need a Peer to implement the Dealer or Broler roles, or both.

For example, using the built-in Crossbar router to act as an RPC Dealer.

	In [1]: from wampy.testing.routers import Crossbar

	In [2]: crossbar = Crossbar(
	   ...: 	host='localhost',
       ...: 	config_path='./wampy/testing/routers/config.json',
       ...: 	crossbar_directory='./'
       ...: )

    In [3]: crossbar.start()

    ... watch plenty of Crossbar.io logging ouput fly by....

A client (either a Caller or a Callee) can then begin a Session with the Router.

	In [3]: from wampy.peers.clients import ClientBase

	In [4]: class DateService(ClientBase):
	   ...: 	""" A service that tells you todays date """
	   ...: 	
	   ...: 	    @property
	   ...: 	    def name(self):
	   ...: 	        return 'Date Service'
	   ...: 	
	   ...: 	    @rpc
	   ...: 	    def get_todays_date(self):
	   ...: 	        logger.info('getting todays date')
	   ...: 	        return datetime.date.today().isoformat()

	In [5]: from wampy.constants import DEFAULT_REALM, DEFAULT_ROLES

	In [6]: service = DateService(
        name="Date Service", router=crossbar,
        realm=DEFAULT_REALM, roles=DEFAULT_ROLES,
    )

	In [7]: service.start()

	In [8]: service.session.id
	Out[8]: 3941615218422338


If a Peer implements the "Callee" Role, then by starting the Peer you instruct the Peer to register its RPC entrypoints with the Router.

	In [9]: service.role
	Out[9]: 'CALLEE' 

	In [10]: from wampy.registry import get_registered_entrypoints
	Out[10]: {347361574427174: (wampy.testing.clients.callees.DateService, 'get_todays_date')}

Any method of the Peer decorated with @rpc will have been registered as publically availabile over the Router.

	In [11]: from wampy.testing.clients.callers import StandAloneClient

	In [12]: client = StandAloneClient(
        name="Caller", router=crossbar,
        realm=DEFAULT_REALM, roles=DEFAULT_ROLES,
    )

The built in stand alone client knows about the entrypoints made available by the ``DateService`` and using it you can call them directly.

	In [13]: client.rpc(procedure="get_todays_date")
	Out [13]: u'2016-05-14'

When you're done playing, stop the Router, as it is running in a subprocess and needs to be managed carefully.

	In [14]: crossbar.stop()

	In [15]: exit()
