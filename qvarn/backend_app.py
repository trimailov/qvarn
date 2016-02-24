# backend_app.py - implement main parts of a backend application
#
# Copyright 2015, 2016 Suomen Tilaajavastuu Oy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import argparse
import bottle
import ConfigParser
import logging
import logging.handlers
import sys

import qvarn


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
        self._dbconn = None
        self._vs = None
        self._resources = []
        self._conf = None

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

    def prepare_for_uwsgi(self):
        '''Prepare the application to be run by uwsgi.

        Return a Bottle application that uwsgi can use. The caller
        should assign it to a global variable called "application", or
        some other name uwsgi is configured to use.

        '''

        # The actual running is in run_helper. Here we just catch
        # exceptions and handle them in some useful manner.

        try:
            self.run_helper()
        except SystemExit as e:
            sys.exit(e.code if type(e.code) == int else 1)
        except BaseException as e:
            logging.critical(str(e), exc_info=True)
            sys.exit(1)
        else:
            return self._app

    def run_helper(self):
        self._conf, args = self._parse_config()

        if args.prepare_storage:
            # Logging should be the first plugin (outermost wrapper)
            self._configure_logging(self._conf)
            self._connect_to_storage(self._conf)
            self._prepare_storage(self._conf)
        else:
            # Logging should be the first plugin (outermost wrapper)
            self._configure_logging(self._conf)
            self._install_logging_plugin()
            # Error catching should also be as high as possible to catch all
            self._app.install(qvarn.ErrorTransformPlugin())
            self._setup_auth(self._conf)
            self._app.install(qvarn.StringToUnicodePlugin())
            # Import is here to not fail tests and is only used on uWSGI
            import uwsgidecorators
            uwsgidecorators.postfork(self._uwsgi_postfork_setup)

    def _uwsgi_postfork_setup(self):
        '''Setup after uWSGI has forked the process.

        We create the database connection pool after uWSGI has forked the
        process to not share the pool connections between processes.

        '''
        self._connect_to_storage(self._conf)
        routes = self._prepare_resources()
        self.add_routes(routes)

    def _parse_config(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '--prepare-storage',
            action='store_true',
            help='only prepare database storage')
        parser.add_argument(
            '--config',
            metavar='FILE',
            help='use FILE as configuration file')
        args = parser.parse_args()

        config = ConfigParser.RawConfigParser()
        config.read(args.config)
        return config, args

    def _connect_to_storage(self, conf):
        '''Prepare the database for use.'''

        sql = qvarn.PostgresAdapter(
            host=conf.get('database', 'host'),
            port=conf.get('database', 'port'),
            db_name=conf.get('database', 'name'),
            user=conf.get('database', 'user'),
            password=conf.get('database', 'password'),
            min_conn=conf.get('database', 'minconn'),
            max_conn=conf.get('database', 'maxconn'),
        )

        self._dbconn = qvarn.DatabaseConnection()
        self._dbconn.set_sql(sql)

    def _prepare_storage(self, conf):
        '''Prepare the database for use.'''
        if not conf.getboolean('database', 'readonly'):
            with self._dbconn.transaction() as t:
                self._vs.prepare_storage(t)

    def _configure_logging(self, conf):
        format_string = ('%(asctime)s %(process)d.%(thread)d %(levelname)s '
                         '%(message)s')
        if conf.has_option('main', 'log'):
            # TODO: probably add rotation parameters to conf file
            # Also possible to use fileConfig() directly for this.
            log = logging.getLogger()
            log.setLevel(logging.DEBUG)

            max_bytes = 10 * 1024**2
            if conf.has_option('main', 'log-max-bytes'):
                max_bytes = conf.getint('main', 'log-max-bytes')

            max_logs = 10
            if conf.has_option('main', 'log-max-files'):
                max_logs = conf.getint('main', 'log-max-files')

            handler = logging.handlers.RotatingFileHandler(
                conf.get('main', 'log'),
                maxBytes=max_bytes,
                backupCount=max_logs)
            handler.setFormatter(logging.Formatter(format_string))
            log.addHandler(handler)
        else:
            logging.basicConfig(level=logging.DEBUG, format=format_string)
        logging.info('========================================')
        logging.info('{} starts'.format(sys.argv[0]))

    def _install_logging_plugin(self):
        logging_plugin = qvarn.LoggingPlugin()
        self._app.install(logging_plugin)

    def _setup_auth(self, conf):
        if (conf.has_option('auth', 'token_validation_key') and
                conf.has_option('auth', 'token_issuer')):

            authorization_plugin = qvarn.AuthorizationPlugin(
                conf.get('auth', 'token_validation_key'),
                conf.get('auth', 'token_issuer'))

            self._app.install(authorization_plugin)

    def _prepare_resources(self):
        routes = []
        for resource in self._resources:
            routes += resource.prepare_resource(self._dbconn)
        return routes