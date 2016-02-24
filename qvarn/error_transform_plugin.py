# error_transform_plugin.py - transforms qvarn.BackendExceptions
#                             to HTTP JSON responses
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


import bottle

import qvarn


class ErrorTransformPlugin(object):

    '''Catches a qvarn.BackendException and returns error as dict instead.

    Uses BackendException error attribute as the to-be-JSONified dict and also
    sets the response error status code to HTTPError status_code.
    '''

    def apply(self, callback, route):
        def wrapper(*args, **kwargs):
            try:
                result = callback(*args, **kwargs)
                return result
            except qvarn.BackendException, e:
                bottle.response.status = e.status_code
                return e.error
        return wrapper