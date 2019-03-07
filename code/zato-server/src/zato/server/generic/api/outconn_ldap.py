# -*- coding: utf-8 -*-

"""
Copyright (C) 2019, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

# stdlib
from codecs import encode
from logging import getLogger
from traceback import format_exc

# Bunch
from bunch import bunchify

# ldap3
from ldap3 import ALL, Connection, EXTERNAL, NTLM, Server, ServerPool, SYNC

# Zato
from zato.common.util import spawn_greenlet
from zato.server.connection.queue import Wrapper

# ################################################################################################################################

# Type hints
import typing

if typing.TYPE_CHECKING:
    from bunch import Bunch

    # For pyflakes
    Bunch = Bunch

# ################################################################################################################################

logger = getLogger(__name__)

# ################################################################################################################################
# ################################################################################################################################

class LDAPClient(object):
    """ A client through which outgoing LDAP messages can be sent.
    """
    def __init__(self, config):
        # type: (Bunch) -> None

        self.config = config
        self.is_connected = False
        self.impl = None # type: Connection
        spawn_greenlet(self._init, timeout=2)

# ################################################################################################################################

    def _init(self):

        # All servers in our pool, even if there is only one
        servers = []

        for server_info in self.config.server_list: # type: str

            # Configuration for each server
            server_config = {
                'host': server_info,
                'use_ssl': self.config.is_tls_enabled,
                'get_info': self.config.get_info,
                'connect_timeout': self.config.connect_timeout,
                'mode': self.config.ip_mode,
            }

            # Create a server object and append it to the list given to the pool later on
            servers.append(Server(**server_config))

        # Configuration for the server pool
        pool_config = {
            'servers': servers,
            'pool_strategy': self.config.pool_ha_strategy,
            'active': self.config.pool_max_cycles,
            'exhaust': self.config.pool_exhaust_timeout
        }

        # Create our server pool
        pool = ServerPool(**pool_config)

        # Connection configuration
        conn_config = {
            'server': pool,
            'user': self.config.username,
            'password': self.config.secret,
            'auto_bind': self.config.auto_bind,
            'auto_range': self.config.use_auto_range,
            'client_strategy': SYNC,
            'sasl_mechanism': EXTERNAL if self.config.use_sasl_external else None,
            'check_names': self.config.should_check_names,
            'collect_usage': self.config.is_stats_enabled,
            'read_only': self.config.is_read_only,
            'pool_name': self.config.pool_name or encode(self.config.name),
            'pool_size': self.config.pool_size,
            'pool_lifetime': self.config.pool_lifetime,
            'return_empty_attributes': self.config.should_return_empty_attrs,
            'pool_keepalive': self.config.pool_keep_alive,
        }

        # Finally, create the connection objet
        self.impl = Connection(**conn_config)

        # If we are active, bind and run a ping query immediately to check if any server is actually available
        if self.config.is_active:
            self.impl.bind()
            self.ping()

# ################################################################################################################################

    def delete(self):
        self.impl.unbind()

# ################################################################################################################################

    def ping(self):
        logger.info('Pinging LDAP `%s`', self.config.server_list)
        out = self.impl.abandon(0)

# ################################################################################################################################
# ################################################################################################################################

class OutconnLDAPWrapper(Wrapper):
    """ Wraps a queue of connections to LDAP.
    """
    def __init__(self, config, server):
        config.parent = self
        super(OutconnLDAPWrapper, self).__init__(config, 'outgoing LDAP', server)

# ################################################################################################################################

    def change_password(self, msg):
        logger.warn('QQQ %s', msg)

# ################################################################################################################################

    def ping(self):
        with self.client() as client:
            client.ping()

# ################################################################################################################################

    def add_client(self):
        try:
            conn = LDAPClient(self.config)
        except Exception:
            logger.warn('LDAP client could not be built `%s`', format_exc())
        else:
            self.client.put_client(conn)

# ################################################################################################################################
