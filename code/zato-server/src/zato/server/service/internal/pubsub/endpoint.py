# -*- coding: utf-8 -*-

"""
Copyright (C) 2017, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

# stdlib
from contextlib import closing

# SQLAlchemy

# Zato
from zato.common import PUBSUB as COMMON_PUBSUB
from zato.common.broker_message import PUBSUB
from zato.common.exception import BadRequest
from zato.common.odb.model import PubSubEndpoint, PubSubEndpointEnqueuedMessage, PubSubEndpointTopic, PubSubSubscription, PubSubTopic
from zato.common.odb.query import count, pubsub_endpoint, pubsub_endpoint_queue, pubsub_endpoint_queue_list, pubsub_endpoint_list
from zato.common.util import new_cid
from zato.server.service import AsIs, Int
from zato.server.service.internal import AdminService, AdminSIO
from zato.server.service.meta import CreateEditMeta, DeleteMeta, GetListMeta

# ################################################################################################################################

elem = 'pubsub_endpoint'
model = PubSubEndpoint
label = 'a pub/sub endpoint'
broker_message = PUBSUB
broker_message_prefix = 'ENDPOINT_'
list_func = pubsub_endpoint_list
skip_input_params = ['is_internal', 'sub_key']
output_optional_extra = ['ws_channel_name', 'hook_service_name', 'sec_id', 'sec_type', 'sec_name', 'sub_key']

# ################################################################################################################################

def instance_hook(self, input, instance, attrs):

    if attrs.is_delete:
        return

    # Don't use empty string with integer attributes, set them to None (NULL) instead
    if instance.service_id == '':
        instance.service_id = None

    # SQLite will not accept empty strings, must be None
    instance.last_seen = instance.last_seen or None
    instance.last_pub_time = instance.last_pub_time or None
    instance.last_sub_time = instance.last_sub_time or None
    instance.last_deliv_time = instance.last_deliv_time or None

    #
    # 1) If role indicates a subscriber but sub_key doesn't exist, we need to create a new one.
    #
    # 2) If sub_key exists and role indicates a subscriber, we don't do anything
    #    because this is a valid sub_key.
    #
    # 3) If role doesn't indicate the instance is a subscriber but sub_key exists,
    #    it means that we need to remove this sub_key from instance because
    #    it used to be a subscriber but is not anymore.
    #

    has_sub_role = 'sub' in input.role

    if has_sub_role:

        # 1)
        if not instance.sub_key:
            instance.sub_key = 'zpsk{}'.format(new_cid())
            input.sub_key = instance.sub_key

        # 2)
        else:
            pass # Explicitly don't do anything

    else:
        # 3)
        if instance.sub_key:
            instance.sub_key = None

def broker_message_hook(self, input, instance, attrs, service_type):
    if service_type == 'create_edit':
        with closing(self.odb.session()) as session:
            input.is_internal = pubsub_endpoint(session, input.cluster_id, instance.id).is_internal

# ################################################################################################################################

class GetList(AdminService):
    _filter_by = PubSubEndpoint.name,
    __metaclass__ = GetListMeta

# ################################################################################################################################

class Create(AdminService):
    __metaclass__ = CreateEditMeta

# ################################################################################################################################

class Edit(AdminService):
    __metaclass__ = CreateEditMeta

# ################################################################################################################################

class Delete(AdminService):
    __metaclass__ = DeleteMeta

# ################################################################################################################################

class Get(AdminService):
    class SimpleIO:
        input_required = ('cluster_id', AsIs('id'))
        output_required = ('id', 'name', 'is_active', 'is_internal', 'role')
        output_optional = ('tags', 'topic_patterns', 'pub_tag_patterns', 'message_tag_patterns',
            'security_id', 'ws_channel_id', 'hook_service_id', 'sec_type', 'sec_name', 'ws_channel_name', 'hook_service_name',
            'sub_key')

    def handle(self):
        with closing(self.odb.session()) as session:
            self.response.payload = pubsub_endpoint(session, self.request.input.cluster_id, self.request.input.id)

# ################################################################################################################################

class GetTopicList(AdminService):
    """ Returns all topics to which a given endpoint published at least once.
    """
    class SimpleIO:
        input_required = ('cluster_id', 'endpoint_id')
        output_required = ('topic_id', 'name', 'is_active', 'is_internal', 'max_depth')
        output_optional = ('last_pub_time', AsIs('last_msg_id'), AsIs('last_correl_id'), 'last_in_reply_to')
        output_repeated = True

    def handle(self):
        input = self.request.input
        pubsub = self.server.worker_store.pubsub
        response = []

        with closing(self.odb.session()) as session:

            # Get last pub time for that specific endpoint to this very topic
            last_data = session.query(
                PubSubTopic.id.label('topic_id'),
                PubSubTopic.name, PubSubTopic.is_active,
                PubSubTopic.is_internal, PubSubTopic.name,
                PubSubTopic.max_depth,
                PubSubEndpointTopic.last_pub_time,
                PubSubEndpointTopic.pub_msg_id.label('last_msg_id'),
                PubSubEndpointTopic.pub_correl_id.label('last_correl_id'),
                PubSubEndpointTopic.in_reply_to.label('last_in_reply_to'),
                ).\
                filter(PubSubEndpointTopic.topic_id==PubSubTopic.id).\
                filter(PubSubEndpointTopic.endpoint_id==input.endpoint_id).\
                filter(PubSubEndpointTopic.cluster_id==self.request.input.cluster_id).\
                all()

            for item in last_data:
                item.last_pub_time = item.last_pub_time.isoformat()
                response.append(item)

        self.response.payload[:] = response

# ################################################################################################################################

class GetEndpointQueueList(AdminService):
    """ Returns all queues to which a given endpoint is subscribed.
    """
    class SimpleIO(AdminSIO):
        input_required = ('cluster_id', 'endpoint_id')
        output_required = ('sub_id', 'topic_id', 'topic_name', 'queue_name', 'active_status', 'is_internal',
            'is_staging_enabled', 'creation_time', 'sub_key', 'has_gd', 'delivery_method',
            'delivery_data_format', 'endpoint_name', Int('total_depth'), Int('current_depth'), Int('staging_depth'))
        output_optional = ('delivery_endpoint', 'last_interaction_time', 'last_interaction_type', 'last_interaction_details', )
        output_repeated = True

    def handle(self):
        response = []

        with closing(self.odb.session()) as session:

            queue_list = pubsub_endpoint_queue_list(session, self.request.input.cluster_id, self.request.input.endpoint_id).\
                all()

            for item in queue_list:

                total_q = session.query(PubSubEndpointEnqueuedMessage.id).\
                    filter(PubSubEndpointEnqueuedMessage.cluster_id==self.request.input.cluster_id).\
                    filter(PubSubEndpointEnqueuedMessage.subscription_id==item.sub_id)

                current_q = session.query(PubSubEndpointEnqueuedMessage.id).\
                    filter(PubSubEndpointEnqueuedMessage.cluster_id==self.request.input.cluster_id).\
                    filter(PubSubEndpointEnqueuedMessage.subscription_id==item.sub_id).\
                    filter(PubSubEndpointEnqueuedMessage.is_in_staging != True)

                staging_q = session.query(PubSubEndpointEnqueuedMessage.id).\
                    filter(PubSubEndpointEnqueuedMessage.cluster_id==self.request.input.cluster_id).\
                    filter(PubSubEndpointEnqueuedMessage.subscription_id==item.sub_id).\
                    filter(PubSubEndpointEnqueuedMessage.is_in_staging == True)

                total_depth = count(session, total_q)
                current_depth = count(session, current_q)
                staging_depth = count(session, staging_q)

                item.total_depth = total_depth
                item.current_depth = current_depth
                item.staging_depth = staging_depth

                item.creation_time = item.creation_time.isoformat()

                if item.last_interaction_time:
                    item.last_interaction_time = item.last_interaction_time.isoformat()
                response.append(item)

        self.response.payload[:] = response

# ################################################################################################################################

class UpdateEndpointQueue(AdminService):
    """ Returns all queues to which a given endpoint is subscribed.
    """
    class SimpleIO(AdminSIO):
        input_required = ('cluster_id', 'id', 'sub_key', 'active_status')
        input_optional = ('is_staging_enabled', 'has_gd')
        output_required = ('id', 'name')

    def handle(self):

        with closing(self.odb.session()) as session:
            item = session.query(PubSubSubscription).\
                filter(PubSubSubscription.id==self.request.input.id).\
                filter(PubSubSubscription.cluster_id==self.request.input.cluster_id).\
                one()

            item.sub_key = self.request.input.sub_key
            item.active_status = self.request.input.active_status
            item.is_staging_enabled = self.request.input.is_staging_enabled
            item.has_gd = self.request.input.has_gd

            session.add(item)
            session.commit()

            self.response.payload.id = self.request.input.id
            self.response.payload.name = item.topic.name

# ################################################################################################################################

class GetEndpointQueue(AdminService):
    class SimpleIO(AdminSIO):
        input_required = ('cluster_id', 'id')
        output_required = ('sub_id', 'topic_id', 'topic_name', 'queue_name', 'active_status', 'is_internal',
            'is_staging_enabled', 'creation_time', 'sub_key', 'has_gd', 'delivery_method',
            'delivery_data_format', 'endpoint_name', Int('total_depth'), Int('current_depth'), Int('staging_depth'))
        output_optional = ('delivery_endpoint', 'last_interaction_time', 'last_interaction_type', 'last_interaction_details', )

    def handle(self):
        with closing(self.odb.session()) as session:
            item = pubsub_endpoint_queue(session, self.request.input.cluster_id, self.request.input.id)

            item.creation_time = item.creation_time.isoformat()
            if item.last_interaction_time:
                item.last_interaction_time = item.last_interaction_time.isoformat()

            self.response.payload = item

# ################################################################################################################################

class ClearEndpointQueue(AdminService):
    """ Clears messages from the queue given on input.
    """
    class SimpleIO(AdminSIO):
        input_required = ('cluster_id', 'id')
        input_optional = ('queue_type',)

    def handle(self, _queue_type=COMMON_PUBSUB.QUEUE_TYPE):

        # Make sure the (optional) queue type is one of allowed values
        queue_type = self.request.input.queue_type

        if queue_type:
            if queue_type not in _queue_type:
                raise BadRequest(self.cid, 'Invalid queue_type:`{}`'.format(queue_type))
            else:
                if queue_type == _queue_type.CURRENT:
                    is_in_staging = False
                elif queue_type == _queue_type.STAGING:
                    is_in_staging = True
        else:
            is_in_staging = None

        # Remove all references to the queue given on input
        with closing(self.odb.session()) as session:
            q = session.query(PubSubEndpointEnqueuedMessage).\
                filter(PubSubEndpointEnqueuedMessage.cluster_id==self.request.input.cluster_id).\
                filter(PubSubEndpointEnqueuedMessage.subscription_id==self.request.input.id)

            if is_in_staging is not None:
                q = q.filter(PubSubEndpointEnqueuedMessage.is_in_staging.is_(is_in_staging))
            q.delete()

            session.commit()

# ################################################################################################################################

class DeleteEndpointQueue(AdminService):
    """ Deletes a given queue for messages - including all messages and their parent subscription object.
    """
    class SimpleIO(AdminSIO):
        input_required = ('cluster_id', 'id')

    def handle(self):

        # Remove the subscription object which in turn cascades and removes all dependant objects
        with closing(self.odb.session()) as session:
            session.query(PubSubSubscription).\
                filter(PubSubSubscription.cluster_id==self.request.input.cluster_id).\
                filter(PubSubSubscription.id==self.request.input.id).\
                delete()

            session.commit()

# ################################################################################################################################
