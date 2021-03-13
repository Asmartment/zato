# -*- coding: utf-8 -*-

"""
Copyright (C) 2021, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

# stdlib
from unittest import main, TestCase

# Faker
from faker import Faker

# gevent
from gevent.lock import RLock

# Zato
from zato.common.ext.dataclasses import dataclass
from zato.server.pattern.base import ParallelBase
from zato.server.pattern.model import ParallelCtx
from zato.server.service import Service

# ################################################################################################################################
# ################################################################################################################################

# Random data to seed our data with
seed = 'FVD2nbPOVIXZ6'

Faker.seed(seed)
fake = Faker()

# ################################################################################################################################
# ################################################################################################################################

class FakeService:
    def __init__(self):
        self.cid = None  # type: int
        self.name = None # type: str

# ################################################################################################################################
# ################################################################################################################################

@dataclass(init=False)
class ParamsCtx:
    cid: object
    source_service: FakeService
    source_name: str

    service_name1: str
    service_name2: str

    service_input1: str
    service_input2: str

    on_final1: str
    on_final2: str

    on_target1: str
    on_target2: str

    targets: list
    on_final_list: list
    on_target_list: list

# ################################################################################################################################
# ################################################################################################################################

class PatternBaseTestCase(TestCase):

    def get_default_params(self):
        # type: () -> ParamsCtx

        cid = fake.pyint()
        source_name = fake.name()

        source_service = FakeService()
        source_service.cid = cid
        source_service.name = source_name

        service_name1 = 'my.service.1'
        service_name2 = 'my.service.2'

        service_input1 = {'my.input': '1'}
        service_input2 = {'my.input': '2'}

        on_final1 = 'on.final.1'
        on_final2 = 'on.final.2'

        on_target1 = 'on.target.1'
        on_target2 = 'on.target.2'

        targets = {
            service_name1: service_input1,
            service_name2: service_input2,
        }

        on_final_list = [
            on_final1,
            on_final2
        ]

        on_target_list = [
            on_target1,
            on_target2
        ]

        ctx = ParamsCtx()
        ctx.cid = cid
        ctx.source_service = source_service
        ctx.source_name = source_name

        ctx.service_name1 = service_name1
        ctx.service_name2 = service_name2

        ctx.service_input1 = service_input1
        ctx.service_input2 = service_input2

        ctx.on_final1 = on_final1
        ctx.on_final2 = on_final2

        ctx.on_target1 = on_target1
        ctx.on_target2 = on_target2

        ctx.targets = targets
        ctx.on_final_list = on_final_list
        ctx.on_target_list = on_target_list

        return ctx

# ################################################################################################################################

    def xtest_base_parallel_invoke_params_no_cid(self):

        params_ctx = self.get_default_params()

        cache = {}
        lock = RLock()

        def xtest_invoke(ctx):
            # type: (ParallelCtx) -> None

            self.assertEqual(ctx.cid, params_ctx.cid)
            self.assertEqual(ctx.source_name, params_ctx.source_name)
            self.assertDictEqual(ctx.target_list, params_ctx.targets)
            self.assertListEqual(ctx.on_final_list, params_ctx.on_final_list)
            self.assertListEqual(ctx.on_target_list, params_ctx.on_target_list)

        api = ParallelBase(params_ctx.source_service, cache, lock)
        api._invoke = test_invoke
        api.invoke(params_ctx.targets, params_ctx.on_final_list, params_ctx.on_target_list)

# ################################################################################################################################

    def xtest_base_parallel_invoke_params_with_cid(self):

        params_ctx = self.get_default_params()
        custom_cid = fake.pystr()

        cache = {}
        lock = RLock()

        def xtest_invoke(ctx):
            # type: (ParallelCtx) -> None

            self.assertEqual(ctx.cid, custom_cid)
            self.assertEqual(ctx.source_name, params_ctx.source_name)
            self.assertDictEqual(ctx.target_list, params_ctx.targets)
            self.assertListEqual(ctx.on_final_list, params_ctx.on_final_list)
            self.assertListEqual(ctx.on_target_list, params_ctx.on_target_list)

        api = ParallelBase(params_ctx.source_service, cache, lock)
        api._invoke = test_invoke
        api.invoke(params_ctx.targets, params_ctx.on_final_list, params_ctx.on_target_list, custom_cid)

# ################################################################################################################################

    def xtest_base_parallel_invoke_params_single_elements(self):

        params_ctx = self.get_default_params()
        custom_on_final = fake.pystr()
        custom_on_target = fake.pystr()

        cache = {}
        lock = RLock()

        def xtest_invoke(ctx):
            # type: (ParallelCtx) -> None

            self.assertEqual(ctx.cid, params_ctx.cid)
            self.assertEqual(ctx.source_name, params_ctx.source_name)
            self.assertDictEqual(ctx.target_list, params_ctx.targets)
            self.assertListEqual(ctx.on_final_list, [custom_on_final])
            self.assertListEqual(ctx.on_target_list, [custom_on_target])

        api = ParallelBase(params_ctx.source_service, cache, lock)
        api._invoke = test_invoke
        api.invoke(params_ctx.targets, custom_on_final, custom_on_target)

# ################################################################################################################################

    def xtest_base_parallel_invoke_params_final_is_none(self):

        params_ctx = self.get_default_params()
        custom_on_final = None
        custom_on_target = fake.pystr()

        cache = {}
        lock = RLock()

        def xtest_invoke(ctx):
            # type: (ParallelCtx) -> None

            self.assertEqual(ctx.cid, params_ctx.cid)
            self.assertEqual(ctx.source_name, params_ctx.source_name)
            self.assertDictEqual(ctx.target_list, params_ctx.targets)
            self.assertIsNone(ctx.on_final_list)
            self.assertListEqual(ctx.on_target_list, [custom_on_target])

        api = ParallelBase(params_ctx.source_service, cache, lock)
        api._invoke = test_invoke
        api.invoke(params_ctx.targets, custom_on_final, custom_on_target)

# ################################################################################################################################

    def xtest_base_parallel_invoke_params_target_is_none(self):

        params_ctx = self.get_default_params()
        custom_on_final = fake.pystr()
        custom_on_target = None

        cache = {}
        lock = RLock()

        def xtest_invoke(ctx):
            # type: (ParallelCtx) -> None

            self.assertEqual(ctx.cid, params_ctx.cid)
            self.assertEqual(ctx.source_name, params_ctx.source_name)
            self.assertDictEqual(ctx.target_list, params_ctx.targets)
            self.assertListEqual(ctx.on_final_list, [custom_on_final])
            self.assertIsNone(ctx.on_target_list)

        api = ParallelBase(params_ctx.source_service, cache, lock)
        api._invoke = test_invoke
        api.invoke(params_ctx.targets, custom_on_final, custom_on_target)

# ################################################################################################################################

    def test_base_invoke_callback_all(self):

        params_ctx = self.get_default_params()

        cache = {}
        lock = RLock()

        api = ParallelBase(params_ctx.source_service, cache, lock)
        api.invoke(params_ctx.targets, params_ctx.on_final_list, params_ctx.on_target_list)

# ################################################################################################################################
# ################################################################################################################################

if __name__ == '__main__':
    main()

# ################################################################################################################################
