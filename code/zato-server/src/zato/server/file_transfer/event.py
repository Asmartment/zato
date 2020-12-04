# -*- coding: utf-8 -*-

"""
Copyright (C) Zato Source s.r.o. https://zato.io

Licensed under LGPLv3, see LICENSE.txt for terms and conditions.
"""

# stdlib
import os
from logging import getLogger
from traceback import format_exc

# Zato
from zato.common.util.api import hot_deploy, spawn_greenlet

if 0:
    from zato.server.file_transfer.observer.base import BaseObserver
    from zato.server.file_transfer.snapshot import BaseSnapshotMaker

    BaseObserver = BaseObserver
    BaseSnapshotMaker = BaseSnapshotMaker

# ################################################################################################################################
# ################################################################################################################################_s

logger = getLogger('zato')

# ################################################################################################################################
# ################################################################################################################################_s

singleton = object()

# ################################################################################################################################
# ################################################################################################################################

class FileTransferEvent(object):
    """ Encapsulates information about a file picked up from file system.
    """
    __slots__ = ('base_dir', 'file_name', 'full_path', 'channel_name', 'ts_utc', 'raw_data', 'data', 'has_raw_data', 'has_data',
        'parse_error')

    def __init__(self):
        self.base_dir = None      # type: str
        self.file_name = None     # type: str
        self.full_path = None     # type: str
        self.channel_name = None  # type: str
        self.ts_utc = None        # type: str
        self.raw_data = ''        # type: str
        self.data = singleton     # type: str
        self.has_raw_data = False # type: bool
        self.has_data = False     # type: bool
        self.parse_error = None   # type: str

# ################################################################################################################################
# ################################################################################################################################

class FileTransferEventHandler:

    def __init__(self, manager, channel_name, config):
        # type: (FileTransferAPI, str, Bunch) -> None

        self.manager = manager
        self.channel_name = channel_name
        self.config = config

    def on_created(self, transfer_event, observer, snapshot_maker=None):
        # type: (PathCreatedEvent, BaseObserver, BaseSnapshotMaker) -> None

        try:

            logger.warn('WWW-1')

            # Ignore the event if it points to the directory itself,
            # as inotify will send CLOSE_WRITE when it is not a creation of a file
            # but a fact that a directory has been deleted that the event is about.
            # Note that we issue a log entry only if the path is not one of what
            # we observe, i.e. when one of our own directories is deleted, we do not log it here.

            # The path must have existed since we are being called
            # and we need to check why it does not exist anymore ..
            if not observer.path_exists(transfer_event.src_path, snapshot_maker):

                logger.warn('WWW-2-1 %s', observer)
                logger.warn('WWW-2-2 %s', snapshot_maker)

                # .. if this type of an observer does not wait for paths, we can return immediately ..
                if not observer.should_wait_for_deleted_paths:
                    logger.warn('WWW-3 %s', transfer_event.src_path)
                    return

                # .. if it is one of the paths that we observe, it means that it has been just deleted,
                # so we need to run a background inspector which will wait until it is created once again ..
                if transfer_event.src_path in self.config.pickup_from_list:
                    logger.warn('WWW-4')
                    self.manager.wait_for_deleted_path(transfer_event.src_path)

                else:
                    logger.warn('WWW-5')
                    logger.info('Ignoring local file event; path not found `%s` (%r)', transfer_event.src_path, self.config.name)

                # .. in either case, there is nothing else we can do here.
                logger.warn('WWW-6')
                return

            # Get file name to check if we should handle it ..
            file_name = os.path.basename(transfer_event.src_path) # type: str

            logger.warn('WWW-7')

            # .. return if we should not.
            if not self.manager.should_handle(self.config.name, file_name):
                logger.warn('WWW-8')
                return

            event = FileTransferEvent()
            event.full_path = transfer_event.src_path
            event.base_dir = os.path.dirname(transfer_event.src_path)
            event.file_name = file_name
            event.channel_name = self.channel_name

            logger.warn('WWW-9')

            if self.config.is_hot_deploy:
                spawn_greenlet(hot_deploy, self.manager.server, event.file_name, event.full_path,
                    self.config.should_delete_after_pickup)
                return

            logger.warn('WWW-10')

            if self.config.should_read_on_pickup:

                if snapshot_maker:
                    raw_data = snapshot_maker.get_file_data(event.full_path)
                else:
                    f = open(event.full_path, 'rb')
                    raw_data = f.read()
                    f.close

                event.raw_data = raw_data.decode(self.config.data_encoding) # type: str
                event.has_raw_data = True

                logger.warn('WWW-11')

                if self.config.should_parse_on_pickup:

                    try:
                        event.data = self.manager.get_parser(self.config.parse_with)(event.raw_data)
                        event.has_data = True
                    except Exception:
                        event.parse_error = format_exc()

            # Invokes all callbacks for the event
            spawn_greenlet(self.manager.invoke_callbacks, event, self.config.service_list, self.config.topic_list,
                self.config.outconn_rest_list)

            # Performs cleanup actions
            self.manager.post_handle(event, self.config, observer, snapshot_maker)

        except Exception:
            logger.warn('Exception in pickup event handler `%s` (%s) `%s`',
                self.config.name, transfer_event.src_path, format_exc())

    on_modified = on_created

# ################################################################################################################################
# ################################################################################################################################
