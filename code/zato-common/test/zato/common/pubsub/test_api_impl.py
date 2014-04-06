# -*- coding: utf-8 -*-

"""
Copyright (C) 2014 Dariusz Suchojad <dsuch at zato.io>

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

# stdlib
from json import loads
from datetime import datetime
from unittest import TestCase

# datadiff
from datadiff.tools import assert_equal

# dateutil
from dateutil.parser import parse

# Zato
from zato.common import PUB_SUB
from zato.common.log_message import CID_LENGTH
from zato.common.pubsub import AckCtx, Client, Consumer, GetCtx, Message, PubCtx, PubSubAPI, RedisPubSub, RejectCtx, SubCtx, Topic
from zato.common.test import rand_bool, rand_date_utc, rand_int, rand_string
from .common import RedisPubSubCommonTestCase

class RedisPubSubAPITestCase(RedisPubSubCommonTestCase):

    def setUp(self):
        super(RedisPubSubAPITestCase, self).setUp()
        self.api = PubSubAPI(RedisPubSub(self.kvdb, self.key_prefix))

# ################################################################################################################################

    def _publish_move(self, move=True, **kwargs):
        payload = rand_string()

        topic = Topic(rand_string())
        self.api.add_topic(topic)

        producer = Client(rand_int(), rand_string())
        self.api.add_producer(producer, topic)

        ctx = self.api.publish(payload, topic.name, client_id=producer.id, **kwargs)
        if move:
            self.api.impl.move_to_target_queues()

        return payload, topic, producer, ctx

    def _check_publish(self, **kwargs):

        if kwargs:
            expected_mime_type = kwargs['mime_type']
            expected_priority = kwargs['priority']
            expected_expiration = kwargs['expiration']
            expected_msg_id = kwargs['msg_id']
        else:
            expected_mime_type = PUB_SUB.DEFAULT_MIME_TYPE
            expected_priority = PUB_SUB.DEFAULT_PRIORITY
            expected_expiration = PUB_SUB.DEFAULT_EXPIRATION
            expected_msg_id = None

        payload, topic, producer, ctx = self._publish_move(**kwargs)

        now = datetime.utcnow()

        # ########################################################################################################################
        #
        # MSG_METADATA_KEY
        #
        # ########################################################################################################################

        msg_metadata_dict = self.kvdb.hgetall(self.api.impl.MSG_METADATA_KEY)

        # E.g. {'K0321C8Q5X67N7K2D642ZYZCXY5T': '{"topic": "ab3ee73838d174cd690a1947b56f67674", "priority": 5, "expiration": 60.0,
        #                 "producer": "a951ec619d0f449969529c0bfe8f7900f",
        #                 "creation_time_utc": "2014-04-06T19:51:37.784905", "msg_id": "K0321C8Q5X67N7K2D642ZYZCXY5T",
        #                 "expire_at_utc": "2014-04-06T19:52:37.784905", "mime_type": "text/plain"}'}

        self.assertEquals(len(msg_metadata_dict), 1)
        self.assertTrue(ctx.msg.msg_id in msg_metadata_dict)

        msg_metadata = loads(msg_metadata_dict[ctx.msg.msg_id])

        self.assertEquals(msg_metadata['mime_type'], expected_mime_type)
        self.assertEquals(msg_metadata['priority'], expected_priority)
        self.assertEquals(msg_metadata['expiration'], expected_expiration)
        self.assertEquals(msg_metadata['topic'], topic.name)
        self.assertEquals(msg_metadata['producer'], producer.name)

        creation_time_utc = parse(msg_metadata['creation_time_utc'])
        expire_at_utc = parse(msg_metadata['expire_at_utc'])

        self.assertTrue(creation_time_utc < now, 'creation_time_utc:`{}` is not less than now:`{}`'.format(creation_time_utc, now))
        self.assertTrue(expire_at_utc > now, 'creation_time_utc:`{}` is not greater than now:`{}`'.format(expire_at_utc, now))

        # ########################################################################################################################
        #
        # LAST_PUB_TIME_KEY
        #
        # ########################################################################################################################

        last_pub_time = self.kvdb.hgetall(self.api.impl.LAST_PUB_TIME_KEY)
        self.assertEquals(len(last_pub_time), 1)
        last_pub_time = parse(last_pub_time[topic.name])
        self.assertTrue(last_pub_time < now, 'last_pub_time:`{}` is not less than now:`{}`'.format(last_pub_time, now))

        # ########################################################################################################################
        #
        # MSG_EXPIRE_AT_KEY
        #
        # ########################################################################################################################

        msg_expire_at = self.kvdb.hgetall(self.api.impl.MSG_EXPIRE_AT_KEY)
        self.assertEquals(len(msg_expire_at), 1)
        msg_expire_at = parse(msg_expire_at[ctx.msg.msg_id])
        self.assertTrue(msg_expire_at > now, 'msg_expire_at:`{}` is not greater than now:`{}`'.format(msg_expire_at, now))

        # ########################################################################################################################
        #
        # LAST_SEEN_PRODUCER_KEY
        #
        # ########################################################################################################################

        last_seen_producer = self.kvdb.hgetall(self.api.impl.LAST_SEEN_PRODUCER_KEY)
        self.assertEquals(len(last_seen_producer), 1)
        last_seen_producer = parse(last_seen_producer[str(producer.id)])
        self.assertTrue(last_seen_producer < now, 'last_seen_producer:`{}` is not less than now:`{}`'.format(last_seen_producer, now))

        # ########################################################################################################################
        #
        # MSG_VALUES_KEY
        #
        # ########################################################################################################################

        msg_values = self.kvdb.hgetall(self.api.impl.MSG_VALUES_KEY)
        self.assertEquals(len(msg_values), 1)
        self.assertEquals(payload, msg_values[ctx.msg.msg_id])

    def xtest_publish_defaults(self):
        self._check_publish()

    def xtest_publish_custom_attrs(self):
        self._check_publish(**{
            'mime_type': rand_string(),
            'priority': rand_int(),
            'expiration': rand_int(1000, 2000),
            'msg_id': rand_string(),
        })

# ################################################################################################################################

    def xtest_subscribe(self):
        client_id, client_name = rand_int(), rand_string()
        client = Client(client_id, client_name)
        topics = rand_string(rand_int())

        sub_key = self.api.subscribe(client.id, topics)

        self.assertEquals(self.api.impl.sub_to_cons[sub_key], client_id)
        self.assertEquals(self.api.impl.cons_to_sub[client_id], sub_key)
        self.assertEquals(sorted(self.api.impl.cons_to_topic[client_id]), sorted(topics))

        for topic in topics:
            self.assertIn(client_id, self.api.impl.topic_to_cons[topic])

# ################################################################################################################################

    def _check_consumer_queue_before_get(self, ctx, sub_key):

        # ########################################################################################################################
        #
        # UNACK_COUNTER_KEY
        #
        # ########################################################################################################################

        unack_counter = self.kvdb.hgetall(self.api.impl.UNACK_COUNTER_KEY)
        self.assertEquals(len(unack_counter), 1)
        self.assertEqual(unack_counter[ctx.msg.msg_id], '1') # One subscriber hence one undelivered message

        # ########################################################################################################################
        #
        # CONSUMER_MSG_IDS_PREFIX
        #
        # ########################################################################################################################

        consumer_msg_ids = self.kvdb.lrange(self.api.impl.CONSUMER_MSG_IDS_PREFIX.format(sub_key), 0, -1)
        self.assertEquals(consumer_msg_ids, [ctx.msg.msg_id])

    def _check_get(self, ctx, sub_key, topic, producer, client):

        msg = list(self.api.get(sub_key))[0].to_dict()
        self.assertEquals(msg['topic'], topic.name)
        self.assertEquals(msg['priority'], PUB_SUB.DEFAULT_PRIORITY)
        self.assertEquals(msg['expiration'], PUB_SUB.DEFAULT_EXPIRATION)
        self.assertEquals(msg['producer'], producer.name)
        self.assertEquals(msg['msg_id'], ctx.msg.msg_id)
        self.assertEquals(msg['mime_type'], PUB_SUB.DEFAULT_MIME_TYPE)

        now = datetime.utcnow()

        creation_time_utc = parse(msg['creation_time_utc'])
        expire_at_utc = parse(msg['expire_at_utc'])

        self.assertTrue(creation_time_utc < now, 'creation_time_utc:`{}` is not less than now:`{}`'.format(creation_time_utc, now))
        self.assertTrue(expire_at_utc > now, 'creation_time_utc:`{}` is not greater than now:`{}`'.format(expire_at_utc, now))

        # ########################################################################################################################
        #
        # LAST_SEEN_CONSUMER_KEY
        #
        # ########################################################################################################################

        last_seen_consumer = self.kvdb.hgetall(self.api.impl.LAST_SEEN_CONSUMER_KEY)
        self.assertEquals(len(last_seen_consumer), 1)
        last_seen_consumer = parse(last_seen_consumer[str(client.id)])
        self.assertTrue(last_seen_consumer < now, 'last_seen_consumer:`{}` is not less than now:`{}`'.format(last_seen_consumer, now))

        # ########################################################################################################################
        #
        # CONSUMER_IN_FLIGHT_IDS_PREFIX
        #
        # ########################################################################################################################

        consumer_id_flight_ids = self.kvdb.smembers(self.api.impl.CONSUMER_IN_FLIGHT_IDS_PREFIX.format(sub_key))
        self.assertEquals(len(consumer_id_flight_ids), 1)
        self.assertEqual(list(consumer_id_flight_ids), [ctx.msg.msg_id])

        # ########################################################################################################################
        #
        # CONSUMER_IN_FLIGHT_DATA_PREFIX
        #
        # ########################################################################################################################

        consumer_in_flight_data = self.kvdb.hgetall(self.api.impl.CONSUMER_IN_FLIGHT_DATA_PREFIX.format(sub_key))
        self.assertEquals(len(consumer_in_flight_data), 1)
        consumer_in_flight_data = parse(consumer_in_flight_data[ctx.msg.msg_id])
        self.assertTrue(
            consumer_in_flight_data < now, 'consumer_in_flight_data:`{}` is not less than now:`{}`'.format(
                consumer_in_flight_data, now))

        # There should still be one unacknowledged message.

        unack_counter = self.kvdb.hgetall(self.api.impl.UNACK_COUNTER_KEY)
        self.assertEquals(len(unack_counter), 1)
        self.assertEqual(unack_counter[ctx.msg.msg_id], '1') # One subscriber hence one undelivered message

    def xtest_get_reject_acknowledge(self):
        payload, topic, producer, ctx = self._publish_move(move=False)
        client_id, client_name = rand_int(), rand_string()

        client = Client(client_id, client_name)
        sub_key = self.api.subscribe(client.id, topic.name)

        # Moves a message to the consumer's queue
        self.api.impl.move_to_target_queues()
        self._check_consumer_queue_before_get(ctx, sub_key)

        # Consumer gets a message which puts it in the in-flight state.
        self._check_get(ctx, sub_key, topic, producer, client)

        # However, there should be nothing in the consumer's queue.
        consumer_msg_ids = self.kvdb.lrange(self.api.impl.CONSUMER_MSG_IDS_PREFIX.format(sub_key), 0, -1)
        self.assertEquals(consumer_msg_ids, [])

        # Consumer rejects the message which puts it back on a queue.
        self.api.reject(sub_key, ctx.msg.msg_id)

        # After rejection it's as though the message has just been published.
        self._check_consumer_queue_before_get(ctx, sub_key)

        # Get after rejection works as before.
        self._check_get(ctx, sub_key, topic, producer, client)

        # Consumer acknowledges a message.
        self.api.acknowledge(sub_key, ctx.msg.msg_id)

        # This was the only one subscription so now that the message has been delivered
        # there should be no trace of it in backend.
        # The only keys left are LAST_PUB_TIME_KEY, LAST_SEEN_CONSUMER_KEY and LAST_SEEN_PRODUCER_KEY - nothing else.

        keys = self.kvdb.keys('{}*'.format(self.key_prefix))
        self.assertEquals(len(keys), 3)

        now = datetime.utcnow()

        last_pub_time = parse(self.kvdb.hgetall(self.api.impl.LAST_PUB_TIME_KEY)[topic.name])
        last_seen_consumer = parse(self.kvdb.hgetall(self.api.impl.LAST_SEEN_CONSUMER_KEY)[str(client.id)])
        last_seen_producer = parse(self.kvdb.hgetall(self.api.impl.LAST_SEEN_PRODUCER_KEY)[str(producer.id)])

        self.assertTrue(last_pub_time < now, 'last_pub_time:`{}` is not less than now:`{}`'.format(last_pub_time, now))
        self.assertTrue(last_seen_consumer < now, 'last_seen_consumer:`{}` is not less than now:`{}`'.format(last_seen_consumer, now))
        self.assertTrue(last_seen_producer < now, 'last_seen_producer:`{}` is not less than now:`{}`'.format(last_seen_producer, now))

# ################################################################################################################################

    def test_validate_sub_key(self):
        self.fail()

    def test_publish_exceptions(self):
        self.fail()

    def test_ping(self):
        self.fail()

# ################################################################################################################################

    def xtest_default_clients(self):
        # Initially, default clients are dummy ones.
        default_consumer = self.api.get_default_consumer()
        default_producer = self.api.get_default_producer()

        self.assertEquals(default_consumer.id, None)
        self.assertEquals(default_consumer.name, None)
        self.assertEquals(default_consumer.is_active, True)

        self.assertEquals(default_producer.id, None)
        self.assertEquals(default_producer.name, None)
        self.assertEquals(default_producer.is_active, True)

        cons_id = rand_int()
        cons_name = rand_string()
        cons_is_active = rand_bool()

        prod_name = rand_string()
        prod_id = rand_int()
        prod_is_active = rand_bool()

        cons = Client(cons_id, cons_name, cons_is_active)
        prod = Client(prod_id, prod_name, prod_is_active)

        self.api.set_default_consumer(cons)
        self.api.set_default_producer(prod)

        default_consumer = self.api.get_default_consumer()
        default_producer = self.api.get_default_producer()

        self.assertEquals(default_consumer.id, cons_id)
        self.assertEquals(default_consumer.name, cons_name)
        self.assertEquals(default_consumer.is_active, cons_is_active)

        self.assertEquals(default_producer.id, prod_id)
        self.assertEquals(default_producer.name, prod_name)
        self.assertEquals(default_producer.is_active, prod_is_active)

# ################################################################################################################################

    def xtest_topic_add(self):
        name = rand_string()
        is_active = rand_bool()
        is_fifo = rand_bool()
        max_depth = rand_int()

        topic = Topic(name, is_active, is_fifo, max_depth)

        self.api.add_topic(topic)

        self.assertIn(name, self.api.impl.topics)
        self.assertEquals(len(self.api.impl.topics), 1)

        given = self.api.impl.topics[name]
        self.assertEquals(given.name, name)
        self.assertEquals(given.is_active, is_active)
        self.assertEquals(given.is_fifo, is_fifo)
        self.assertEquals(given.max_depth, max_depth)

        # Adding topic of the same name should not create a new topic because impl.topics is a dictionary
        self.api.add_topic(topic)
        self.assertEquals(len(self.api.impl.topics), 1)

    def xtest_topic_update(self):
        self.test_topic_add() # updating a topic works the same like creating it

# ################################################################################################################################

class CtxObjectsTestCase(TestCase):

    def _get_object(self, class_, kwargs=None):
        return class_(**(kwargs or {}))

# ################################################################################################################################

    def test_add_producer(self):
        self.fail()

    def test_update_producer(self):
        self.fail()

    def test_delete_producer(self):
        self.fail()

    def test_add_consumer(self):
        self.fail()

    def test_update_consumer(self):
        self.fail()

    def test_delete_consumer(self):
        self.fail()

    def test_raising_not_implemented_error(self):
        self.fail()

# ################################################################################################################################

    def xtest_topic_defaults(self):
        name = rand_string()
        topic = self._get_object(Topic, {'name': name})
        self.assertEquals(topic.name, name)
        self.assertEquals(topic.is_active, True)
        self.assertEquals(topic.is_fifo, PUB_SUB.DEFAULT_IS_FIFO)
        self.assertEquals(topic.max_depth, PUB_SUB.DEFAULT_MAX_DEPTH)

    def xtest_topic_custom_attrs(self):
        name = rand_string()
        is_active = rand_bool()
        is_fifo = rand_bool()
        max_depth = rand_int()

        topic = self._get_object(Topic, {
            'name':name, 'is_active':is_active, 'is_fifo':is_fifo, 'max_depth':max_depth
        })

        self.assertEquals(topic.name, name)
        self.assertEquals(topic.is_active, is_active)
        self.assertEquals(topic.is_fifo, is_fifo)
        self.assertEquals(topic.max_depth, max_depth)

# ################################################################################################################################

    def xtest_pub_ctx_defaults(self):
        ctx = PubCtx()
        self.assertEquals(ctx.client_id, None)
        self.assertEquals(ctx.topic, None)
        self.assertEquals(ctx.msg, None)

    def xtest_pub_ctx_custom_attrs(self):
        client_id, topic, msg = rand_string(3)
        ctx = PubCtx(client_id, topic, msg)
        self.assertEquals(ctx.client_id, client_id)
        self.assertEquals(ctx.topic, topic)
        self.assertEquals(ctx.msg, msg)

# ################################################################################################################################

    def xtest_sub_ctx_defaults(self):
        ctx = SubCtx()
        self.assertEquals(ctx.client_id, None)
        self.assertEquals(ctx.topics, [])

    def xtest_sub_ctx_custom_attrs(self):
        client_id, topics = rand_string(2)
        ctx = SubCtx(client_id, topics)
        self.assertEquals(ctx.client_id, client_id)
        self.assertEquals(ctx.topics, topics)

# ################################################################################################################################

    def xtest_get_ctx_defaults(self):
        ctx = GetCtx()
        self.assertEquals(ctx.sub_key, None)
        self.assertEquals(ctx.max_batch_size, PUB_SUB.DEFAULT_GET_MAX_BATCH_SIZE)
        self.assertEquals(ctx.is_fifo, PUB_SUB.DEFAULT_IS_FIFO)
        self.assertEquals(ctx.get_format, PUB_SUB.GET_FORMAT.OBJECT.id)

    def xtest_get_ctx_custom_attrs(self):
        sub_key = rand_string()
        max_batch_size = rand_int()
        is_fifo = rand_bool()
        get_format = rand_string()

        ctx = GetCtx(sub_key, max_batch_size, is_fifo, get_format)

        self.assertEquals(ctx.sub_key, sub_key)
        self.assertEquals(ctx.max_batch_size, max_batch_size)
        self.assertEquals(ctx.is_fifo, is_fifo)
        self.assertEquals(ctx.get_format, get_format)

# ################################################################################################################################

    def xtest_ack_ctx_defaults(self):
        ctx = AckCtx()
        self.assertEquals(ctx.sub_key, None)
        self.assertEquals(ctx.msg_ids, [])

    def xtest_ack_ctx_custom_attrs(self):
        sub_key = rand_string()
        msg_ids = rand_string(2)

        ctx = AckCtx(sub_key, msg_ids)

        self.assertEquals(ctx.sub_key, sub_key)
        self.assertEquals(ctx.msg_ids, msg_ids)

        msg_id = rand_string()
        ctx.append(msg_id)

        self.assertEquals(ctx.msg_ids, msg_ids)

# ################################################################################################################################

    def xtest_reject_ctx_defaults(self):
        ctx = RejectCtx()
        self.assertEquals(ctx.sub_key, None)
        self.assertEquals(ctx.msg_ids, [])

    def xtest_reject_ctx_custom_attrs(self):
        sub_key = rand_string()
        msg_ids = rand_string(2)

        ctx = RejectCtx(sub_key, msg_ids)

        self.assertEquals(ctx.sub_key, sub_key)
        self.assertEquals(ctx.msg_ids, msg_ids)

        msg_id = rand_string()
        ctx.append(msg_id)

        self.assertEquals(ctx.msg_ids, msg_ids)

# ################################################################################################################################

    def xtest_client_defaults(self):
        id, name = rand_int(), rand_string()
        client = Client(id, name)

        self.assertEquals(client.id, id)
        self.assertEquals(client.name, name)
        self.assertEquals(client.is_active, True)

    def xtest_client_custom_attrs(self):
        id, name, is_active = rand_int(), rand_string(), rand_bool()
        client = Client(id, name, is_active)

        self.assertEquals(client.id, id)
        self.assertEquals(client.name, name)
        self.assertEquals(client.is_active, is_active)

# ################################################################################################################################

    def xtest_consumer_defaults(self):
        id, name = rand_int(), rand_string()
        consumer = Consumer(id, name)

        self.assertEquals(consumer.id, id)
        self.assertEquals(consumer.name, name)
        self.assertEquals(consumer.is_active, True)
        self.assertEquals(consumer.sub_key, None)
        self.assertEquals(consumer.max_backlog, PUB_SUB.DEFAULT_MAX_BACKLOG)
        self.assertEquals(consumer.delivery_mode, PUB_SUB.DELIVERY_MODE.PULL.id)
        self.assertEquals(consumer.callback, '')

    def xtest_consumer_custom_attrs(self):
        id = rand_int()
        name = rand_string()
        is_active = rand_bool()
        sub_key = rand_string()
        max_backlog = rand_int()
        delivery_mode = rand_string()
        callback = rand_string()
        consumer = Consumer(id, name, is_active, sub_key, max_backlog, delivery_mode, callback)

        self.assertEquals(consumer.id, id)
        self.assertEquals(consumer.name, name)
        self.assertEquals(consumer.is_active, is_active)
        self.assertEquals(consumer.sub_key, sub_key)
        self.assertEquals(consumer.max_backlog, max_backlog)
        self.assertEquals(consumer.delivery_mode, delivery_mode)
        self.assertEquals(consumer.callback, callback)

# ################################################################################################################################

    def xtest_message_defaults(self):
        msg = self._get_object(Message)
        self.assertEquals(msg.payload, '')
        self.assertEquals(msg.topic, None)
        self.assertEquals(msg.mime_type, PUB_SUB.DEFAULT_MIME_TYPE)
        self.assertEquals(msg.priority, PUB_SUB.DEFAULT_PRIORITY)
        self.assertEquals(msg.expiration, PUB_SUB.DEFAULT_EXPIRATION)
        self.assertEquals(len(msg.msg_id), CID_LENGTH+1) # +1 because CID_LENGTH doesn't take the 'K' prefix into account
        self.assertEquals(msg.producer, None)
        self.assertEquals(msg.expiration, PUB_SUB.DEFAULT_EXPIRATION)

        self.assertIsInstance(msg.creation_time_utc, datetime)
        self.assertLess(msg.creation_time_utc, datetime.utcnow())

        self.assertIsInstance(msg.expire_at_utc, datetime)
        self.assertGreater(msg.expire_at_utc, datetime.utcnow())

        # Used by frontend only
        self.assertEquals(msg.expire_at, None)
        self.assertEquals(msg.payload_html, None)

    def xtest_message_serialization(self):
        msg_id = rand_string()
        creation_time_utc = rand_date_utc()
        expire_at_utc = rand_date_utc()
        producer = rand_string()
        topic = rand_string()

        actual = self._get_object(Message, {
            'msg_id': msg_id,
            'creation_time_utc': creation_time_utc,
            'expire_at_utc': expire_at_utc,
            'producer': producer,
            'topic':topic,
        })

        expected = {
            'mime_type': PUB_SUB.DEFAULT_MIME_TYPE,
            'msg_id': msg_id,
            'topic': topic,
            'expiration': PUB_SUB.DEFAULT_EXPIRATION,
            'producer': producer,
            'creation_time_utc': creation_time_utc.isoformat(),
            'priority': PUB_SUB.DEFAULT_PRIORITY,
            'expire_at_utc': expire_at_utc.isoformat()
        }

        # Dicts must be equal ..
        assert_equal(actual.to_dict(), expected)

        # .. as well as JSON.
        json = actual.to_json()
        self.assertIsInstance(json, str)
        unjsonified = loads(json)
        assert_equal(unjsonified, expected)

# ################################################################################################################################
