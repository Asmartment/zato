# -*- coding: utf-8 -*-

"""
Copyright (C) 2022, Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

# stdlib
import logging

# Zato
from zato.admin.web.views import Index as _Index

from zato.common.marshal_

# ################################################################################################################################
# ################################################################################################################################

if 0:
    from zato.common.typing_ import any_

# ################################################################################################################################
# ################################################################################################################################

logger = logging.getLogger(__name__)

# ################################################################################################################################
# ################################################################################################################################

class action:
    index = 'index'
    default = index

# ################################################################################################################################
# ################################################################################################################################

class Index(_Index):
    method_allowed = 'GET'
    url_name = 'stats-user'
    template = 'zato/stats/user.html'
    service_name = 'stats1.user'
    paginate = True

    def handle_return_data(self, return_data:'any_') -> 'any_':
        return {}

# ################################################################################################################################
# ################################################################################################################################
