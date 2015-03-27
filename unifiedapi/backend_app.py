# backend_app.py - implement main parts of a backend application
#
# Copyright 2015 Suomen Tilaajavastuu Oy
# All rights reserved.


import argparse
import logging
import sys

from flup.server.fcgi import WSGIServer

import unifiedapi.bottle as bottle


class BackendApplication(object):

    '''Main program of a backend application.

    This class provides the logic for command line parsing, log file
    setup, and starting of HTTP service, plus other things that are
    common to all backend applications. Backend applications are
    expected to all have the same external interface, provided by this
    class.

    This class is parameterised by calling the ``set_resource`` and
    ``add_routes`` methods. The application actually starts when the
    ``run`` method is called.

    The ``args`` attribute is public, and can be used to access the
    configuration set by the command line arguments. It is an
    ``argparse`` type.

    '''

    def __init__(self):
        self._app = bottle.app()
        self._resource = None

    def set_resource(self, resource):
        '''Set the resource this application serves.

        The resource is represented by a class that has a
        ``prepare_resource`` method.

        '''

        self._resource = resource

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
        args = self._parse_command_line()
        self._setup_logging(args)
        self._prepare_resource(args)
        self._start_service(args)

    def _parse_command_line(self):
        parser = argparse.ArgumentParser()

        parser.add_argument(
            '--host',
            metavar='ADDR',
            help='use debug HTTP server, bind to ADDR')

        parser.add_argument(
            '--port',
            metavar='PORT',
            type=int,
            help='use debug HTTP server, bind to PORT')

        parser.add_argument(
            '--log',
            metavar='FILE',
            help='write log to FILE')

        parser.add_argument(
            '-d', '--database',
            metavar='FILE',
            help='use FILE as the SQLite3 database')

        return parser.parse_args()

    def _setup_logging(self, args):
        if args.log:
            logging.basicConfig(
                filename=args.log,
                level=logging.DEBUG,
                format='%(asctime)s %(levelname)s %(message)s')
            logging.info('{} starts'.format(sys.argv[0]))

    def _prepare_resource(self, args):
        self._resource.prepare_resource(args.database)

    def _start_service(self, args):
        if not self._start_debug_server(args):
            if not self._start_wsgi_server(args):
                self._die_from_server_confusion()

    def _start_debug_server(self, args):
        if args.host is not None and args.port is not None:
            self._app.run(host=args.host, port=args.port)
            return True

    def _start_wsgi_server(self, args):
        if args.host is None and args.port is None:
            WSGIServer(self._app).run()

    def _die_from_server_confusion(self):
        msg = (
            'Cannot understand which server to start. '
            'Eiher both of of --help and --port must be given, '
            'or neither.')
        logging.error(msg)
        sys.stderr.write('{}\n'.format(msg))
        sys.exit(1)
