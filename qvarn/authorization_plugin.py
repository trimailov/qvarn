# authorization_plugin.py - checks request authorization
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


import qvarn
import bottle


class AuthorizationPlugin(object):

    def __init__(self, token_validation_key, token_issuer):
        self._token_validation_key = token_validation_key
        self._token_issuer = token_issuer
        self._authz_validator = qvarn.AuthorizationValidator()

    def apply(self, callback, route):
        def wrapper(*args, **kwargs):
            self._check_auth()
            self._check_scope()
            return callback(*args, **kwargs)
        return wrapper

    def _check_auth(self):
        access_token = self._authz_validator.get_access_token_from_headers(
            bottle.request.headers)
        result = self._authz_validator.validate_token(
            access_token, self._token_validation_key, self._token_issuer)
        bottle.request.environ[u'scopes'] = result[u'scopes']
        bottle.request.environ[u'client_id'] = result[u'client_id']
        bottle.request.environ[u'user_id'] = result[u'user_id']

    def _check_scope(self):
        scopes = bottle.request.environ['scopes']
        route_scope = self._get_current_scope()
        if not scopes or route_scope not in scopes:
            bottle.response.headers['WWW-Authenticate'] = \
                'Bearer error="insufficient_scope"'
            raise NoAccessToRouteScope(route_scope=route_scope)

    def _get_current_scope(self):
        route_rule = bottle.request.route.rule
        request_method = bottle.request.method
        return qvarn.route_to_scope(route_rule, request_method)


class NoAccessToRouteScope(qvarn.Forbidden):

    msg = u'No access to route scope'