# backend_app.py - implement main parts of a backend application
#
# Copyright 2015 Suomen Tilaajavastuu Oy
# All rights reserved.


import argparse
import bottle
import ConfigParser
import logging
import logging.handlers
import sys

from flup.server.fcgi import WSGIServer

import unifiedapi


class BackendApplication(object):

    '''Main program of a backend application.

    This class provides the logic for command line parsing, log file
    setup, and starting of HTTP service, plus other things that are
    common to all backend applications. Backend applications are
    expected to all have the same external interface, provided by this
    class.

    This class is parameterised by calling the ``set_storage_preparer``,
    ``add_resource`` and ``add_routes`` methods. The application actually
    starts when the ``run`` method is called. The resources added with
    ``add_resource`` MUST have a ``prepare_resource`` method, which gets
    as its parameter the database, and returns a representation
    of routes suitable to be given to ``add_routes``. The resource object
    does not need to call ``add_routes`` directly.

    '''

    def __init__(self):
        self._app = bottle.app()
        self._db = None
        self._vs = None
        self._resources = []

    def set_versioned_storage(self, versioned_storage):
        self._vs = versioned_storage

    def add_resource(self, resource):
        '''Adds a resource that this application serves.

        A resource is represented by a class that has a
        ``prepare_resource`` method.

        '''

        self._resources.append(resource)

    def add_routes(self, routes):
        '''Add routes to the application.

        A route is the path serve (e.g., "/version"), the HTTP method
        ("GET"), and the callback function. The path may use bottle.py
        route syntax to extract parameters from the path.

        The routes are provided as a list of dicts, where each dict
        has the keys ``path``, ``method``, and ``callback``.

        '''

        for route in routes:
            self._app.route(**route)

    def run(self):
        '''Run the application.'''
        conf = self._parse_config()
        # Logging should be the first plugin (outermost wrapper)
        self._setup_logging(conf)
        # Error catching should also be as high as possible to catch all
        self._app.install(unifiedapi.ErrorTransformPlugin())
        self._setup_storage(conf)
        self._setup_auth(conf)
        self._app.install(unifiedapi.StringToUnicodePlugin())
        routes = self._prepare_resources()
        self.add_routes(routes)
        self._start_service(conf)

    def _parse_config(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '--config',
            metavar='FILE',
            help='use FILE as configuration file')
        args = parser.parse_args()

        config = ConfigParser.RawConfigParser()
        config.read(args.config)
        return config

    def _setup_storage(self, conf):
        '''Prepare the database for use.'''
        self._db = unifiedapi.open_disk_database(
            host=conf.get('database', 'host'),
            port=conf.get('database', 'port'),
            db_name=conf.get('database', 'name'),
            user=conf.get('database', 'user'),
            password=conf.get('database', 'password'),
            min_conn=conf.get('database', 'minconn'),
            max_conn=conf.get('database', 'maxconn'))
        if not conf.getboolean('database', 'readonly'):
            assert self._vs
            with self._db:
                self._vs.prepare_storage(self._db)

    def _setup_logging(self, conf):
        format_string = ('%(asctime)s %(levelname)s %(process)d.%(thread)d '
                         '%(message)s')
        if conf.has_option('main', 'log'):
            # TODO: probably add rotation parameters to conf file
            # Also possible to use fileConfig() directly for this.
            log = logging.getLogger()
            log.setLevel(logging.DEBUG)
            handler = logging.handlers.RotatingFileHandler(
                conf.get('main', 'log'),
                maxBytes=10*1024**2,
                backupCount=10)
            handler.setFormatter(
                logging.Formatter(format_string))
            log.addHandler(handler)
        else:
            logging.basicConfig(level=logging.DEBUG, format=format_string)
        logging.info('========================================')
        logging.info('{} starts'.format(sys.argv[0]))
        logging_plugin = unifiedapi.LoggingPlugin()
        self._app.install(logging_plugin)

    def _setup_auth(self, conf):
        if (conf.has_option('auth', 'token_validation_key') and
                conf.has_option('auth', 'token_issuer')):

            authorization_plugin = unifiedapi.AuthorizationPlugin(
                conf.get('auth', 'token_validation_key'),
                conf.get('auth', 'token_issuer'))

            self._app.install(authorization_plugin)

    def _prepare_resources(self):
        routes = []
        for resource in self._resources:
            routes += resource.prepare_resource(self._db)
        return routes

    def _start_service(self, conf):
        if not self._start_debug_server(conf):
            if not self._start_wsgi_server(conf):
                self._die_from_server_confusion()

    def _start_debug_server(self, conf):
        if conf.has_option('main', 'host') and conf.has_option('main', 'port'):
            self._app.run(host=conf.get('main', 'host'),
                          port=conf.get('main', 'port'), quiet=True)
            return True

    def _start_wsgi_server(self, conf):
        if not (conf.has_option('main', 'host') and
                conf.has_option('main', 'port')):
            WSGIServer(self._app).run()
            return True

    def _die_from_server_confusion(self):
        msg = (
            'Cannot understand which server to start. '
            'Eiher both of of --help and --port must be given, '
            'or neither.')
        logging.error(msg)
        sys.stderr.write('{}\n'.format(msg))
        sys.exit(1)
