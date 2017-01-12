# Copyright 2017 QvarnLabs AB
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


import yaml


class ResourceTypeStorage(object):

    _table_name = u'resource_types'

    def prepare_tables(self, transaction):
        transaction.create_table(
            self._table_name,
            {
                u'type': unicode,
                u'yaml': unicode,
            }
        )

    def add_or_update_spec(self, transaction, spec):
        types = self.get_types(transaction)
        if spec[u'type'] in types:
            self._update_spec(transaction, spec)
        else:
            self._add_spec(transaction, spec)

    def _add_spec(self, transaction, spec):
        transaction.insert(
            self._table_name,
            {
                u'type': spec[u'type'],
                u'yaml': yaml.safe_dump(spec),
            }
        )

    def _update_spec(self, transaction, spec):
        transaction.update(
            self._table_name,
            ('=', self._table_name, u'type', spec[u'type']),
            {
                u'type': spec[u'type'],
                u'yaml': yaml.safe_dump(spec),
            }
        )

    def get_types(self, transaction):
        rows = transaction.select(self._table_name, [u'type'], None)
        return [row[u'type'] for row in rows]

    def get_spec(self, transaction, type_name):
        rows = transaction.select(
            self._table_name,
            [u'yaml'],
            ('=', self._table_name, u'type', type_name),
        )
        if len(rows) != 1:  # pragma: no cover
            return None
        return yaml.safe_load(rows[0][u'yaml'])

    def delete_spec(self, transaction, type_name):
        transaction.delete(
            self._table_name,
            ('=', self._table_name, u'type', type_name),
        )
