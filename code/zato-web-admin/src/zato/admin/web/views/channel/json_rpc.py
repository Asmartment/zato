# -*- coding: utf-8 -*-

"""
Copyright (C) 2019, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

# stdlib
import logging
from traceback import format_exc

# Django
from django.http import HttpResponse, HttpResponseServerError
from django.template.response import TemplateResponse

# Zato
from zato.admin.web.forms.channel.json_rpc import CreateForm, EditForm
from zato.admin.web.views import CreateEdit, Delete as _Delete, Index as _Index, method_allowed
from zato.common import ZATO_NONE
from zato.common.util.json_ import dumps

# ################################################################################################################################

logger = logging.getLogger(__name__)

# ################################################################################################################################

class JSONRPC(object):
    def __init__(self):
        self.id = None
        self.name = None
        self.url_path = None
        self.sec_type = None
        self.security_id = None
        self.service_whitelist = None

# ################################################################################################################################

class Index(_Index):
    method_allowed = 'GET'
    url_name = 'channel-json-rpc'
    template = 'zato/channel/json-rpc.html'
    service_name = 'zato.channel.json-rpc.get-list'
    output_class = JSONRPC
    paginate = True

    class SimpleIO(_Index.SimpleIO):
        input_required = 'cluster_id',
        output_required = 'cluster_id', 'id', 'name', 'is_active', 'url_path', 'security_id', 'service_whitelist'
        output_repeated = True

    def on_before_append_item(self, item):

        item.service_whitelist = '\n'.join(item.service_whitelist)

        if item.security_id:
            item.security_id = '{}/{}'.format(item.sec_type, item.security_id)
        else:
            item.security_id = ZATO_NONE
        return item

    def handle(self):
        if self.req.zato.cluster_id:
            sec_list = self.get_sec_def_list('basic_auth').def_items
            sec_list.extend(self.get_sec_def_list('jwt'))
            sec_list.extend(self.get_sec_def_list('vault_conn_sec'))
        else:
            sec_list = []

        return {
            'create_form': CreateForm(sec_list, req=self.req),
            'edit_form': EditForm(sec_list, prefix='edit', req=self.req),
        }

# ################################################################################################################################

class _CreateEdit(CreateEdit):
    method_allowed = 'POST'

    class SimpleIO(CreateEdit.SimpleIO):
        input_required = 'cluster_id', 'name', 'is_active', 'url_path', 'security_id', 'service_whitelist'
        output_required = 'id', 'name'

    def on_after_set_input(self):
        if self.input.security_id != ZATO_NONE:
            self.input.security_id = int(self.input.security_id.split('/')[1])
        else:
            self.input.security_id = None

        service_whitelist = self.input.service_whitelist.strip()
        self.input.service_whitelist = service_whitelist.splitlines()

    def success_message(self, item):
        return 'WebSocket channel `{}` successfully {}'.format(item.name, self.verb)

# ################################################################################################################################

class Create(_CreateEdit):
    url_name = 'channel-json-rpc-create'
    service_name = 'zato.channel.json-rpc.create'

# ################################################################################################################################

class Edit(_CreateEdit):
    url_name = 'channel-json-rpc-edit'
    form_prefix = 'edit-'
    service_name = 'zato.channel.json-rpc.edit'

# ################################################################################################################################

class Delete(_Delete):
    url_name = 'channel-json-rpc-delete'
    error_message = 'Could not delete WebSocket channel'
    service_name = 'zato.channel.json-rpc.delete'

# ################################################################################################################################
