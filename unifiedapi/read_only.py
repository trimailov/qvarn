# read_only.py - read-only interface to databases
#
# Copyright 2015 Suomen Tilaajavastuu Oy
# All rights reserved.


import unifiedapi


class ReadOnlyStorage(object):

    '''Read-only interface to a database.

    You MUST call ``set_db`` and ``set_item_prototype`` before doing
    anything else.

    '''

    def __init__(self):
        self._db = None
        self._item_type = None
        self._prototype = None
        self._subitem_prototypes = unifiedapi.SubItemPrototypes()

    def set_db(self, db):
        '''Set the database to use.'''
        self._db = db

    def set_item_prototype(self, item_type, prototype):
        '''Set type and prototype of items in this database.'''
        self._item_type = item_type
        self._prototype = prototype

    def set_subitem_prototype(self, item_type, subitem_name, prototype):
        '''Set prototype for a subitem.'''
        self._subitem_prototypes.add(item_type, subitem_name, prototype)

    def get_item_ids(self):
        '''Get list of ids of all items.'''
        return [
            row['id']
            for row in self._db.select(self._item_type, [u'id'])]

    def get_item(self, item_id):
        '''Get a specific item.'''
        item = {}
        rw = ReadWalker(self._db, self._item_type, item_id)
        rw.walk_item(item, self._prototype)
        return item

    def get_subitem(self, item_id, subitem_name):
        '''Get a specific subitem.'''
        subitem = {}
        table_name = u'%s_%s' % (self._item_type, subitem_name)
        prototype = self._subitem_prototypes.get(self._item_type, subitem_name)
        rw = ReadWalker(self._db, table_name, item_id)
        rw.walk_item(subitem, prototype)
        return subitem


class ItemDoesNotExist(unifiedapi.BackendException):

    msg = u'Item {id} does not exist'


class ReadWalker(unifiedapi.ItemWalker):

    '''Visit every part of an item to retrieve it from the database.'''

    def __init__(self, db, item_type, item_id):
        self._db = db
        self._item_type = item_type
        self._item_id = item_id

    def visit_main_dict(self, item, column_names):
        row = self._get_row(self._item_type, self._item_id, column_names)
        for name in column_names:
            item[name] = row[name]

    def _get_row(self, table_name, item_id, column_names):
        # If a dict has no non-list fields, column_names is empty.
        # This breaks the self._db.select_matching_rows call below.
        # There's no sensible way to fix the select method, so we look
        # for the id column instead.
        lookup_names = column_names or [u'id']

        match = {
            u'id': item_id
        }
        rows = self._db.select_matching_rows(table_name, lookup_names, match)
        for row in rows:
            # If we don't have any columns, return an empty dict.
            return row if column_names else {}
        raise ItemDoesNotExist(id=item_id)

    def visit_main_str_list(self, item, field):
        table_name = self._db.make_table_name(self._item_type, field)
        item[field] = self._get_str_list(table_name, self._item_id)

    def _get_str_list(self, table_name, item_id):
        rows = self._get_list(table_name, item_id, [u'value'])
        return [row[u'value'] for row in rows]

    def _get_list(self, table_name, item_id, column_names):
        match = {
            u'id': item_id
        }
        rows = self._db.select_matching_rows(
            table_name, [u'list_pos'] + column_names, match)
        in_order = self._sort_rows(rows)
        return self._make_dicts_from_rows(in_order, column_names)

    def _sort_rows(self, rows):
        def get_list_pos(row):
            return row['list_pos']
        return [row for row in sorted(rows, key=get_list_pos)]

    def _make_dicts_from_rows(self, rows, column_names):
        result = []
        for row in rows:
            a_dict = dict((name, row[name]) for name in column_names)
            result.append(a_dict)
        return result

    def visit_main_dict_list(self, item, field, column_names):
        table_name = self._db.make_table_name(self._item_type, field)
        item[field] = self._get_list(table_name, self._item_id, column_names)

    def visit_dict_in_list_str_list(self, item, field, pos, str_list_field):
        table_name = self._db.make_table_name(
            self._item_type, field, str_list_field)

        match = {
            u'id': self._item_id,
            u'dict_list_pos': unicode(pos),
        }
        rows = self._db.select_matching_rows(
            table_name, [u'list_pos', u'value'], match)

        in_order = self._sort_rows(rows)
        result = [row['value'] for row in in_order]
        item[field][pos][str_list_field] = result