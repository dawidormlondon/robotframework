#  Copyright 2008-2015 Nokia Solutions and Networks
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from robot.errors import DataError
from robot.output import LOGGER
from robot.utils import escape, unescape, unic

from .variablesplitter import VariableSplitter


class VariableReplacer(object):

    def __init__(self, variables):
        self._variables = variables

    def replace_list(self, items, replace_until=None):
        """Replaces variables from a list of items.

        If an item in a list is a @{list} variable its value is returned.
        Possible variables from other items are replaced using 'replace_scalar'.
        Result is always a list.

        'replace_until' can be used to limit replacing arguments to certain
        index from the beginning. Used with Run Keyword variants that only
        want to resolve some of the arguments in the beginning and pass others
        to called keywords unmodified.
        """
        items = list(items or [])
        if replace_until is not None:
            return self._replace_list_until(items, replace_until)
        return list(self._replace_list(items))

    def _replace_list_until(self, items, replace_until):
        # @{list} variables can contain more or less arguments than needed.
        # Therefore we need to go through items one by one, and escape possible
        # extra items we got.
        replaced = []
        while len(replaced) < replace_until and items:
            replaced.extend(self._replace_list([items.pop(0)]))
        if len(replaced) > replace_until:
            replaced[replace_until:] = [escape(item)
                                        for item in replaced[replace_until:]]
        return replaced + items

    def _replace_list(self, items):
        for item in items:
            if self._cannot_have_variables(item):
                yield unescape(item)
            else:
                splitter = VariableSplitter(item)
                value = self._replace_scalar(item, splitter)
                if splitter.is_list_variable():
                    for v in value:
                        yield v
                else:
                    yield value

    def replace_scalar(self, item):
        """Replaces variables from a scalar item.

        If the item is not a string it is returned as is. If it is a ${scalar}
        variable its value is returned. Otherwise variables are replaced with
        'replace_string'. Result may be any object.
        """
        if self._cannot_have_variables(item):
            return unescape(item)
        return self._replace_scalar(item)

    def _replace_scalar(self, item, splitter=None):
        if not splitter:
            splitter = VariableSplitter(item)
        if not splitter.identifier:
            return unescape(item)
        if splitter.is_variable():
            return self._get_variable(splitter)
        return self._replace_string(item, splitter)

    def _cannot_have_variables(self, item):
        return not (isinstance(item, basestring) and '{' in item)

    def replace_string(self, string, ignore_errors=False):
        """Replaces variables from a string. Result is always a string."""
        if not isinstance(string, basestring):
            return unic(string)
        if self._cannot_have_variables(string):
            return unescape(string)
        return self._replace_string(string, ignore_errors=ignore_errors)

    def _replace_string(self, string, splitter=None, ignore_errors=False):
        if not splitter:
            splitter = VariableSplitter(string)
        return ''.join(self._yield_replaced(string, splitter, ignore_errors))

    def _yield_replaced(self, string, splitter, ignore_errors=False):
        while splitter.identifier:
            yield unescape(string[:splitter.start])
            try:
                value = self._get_variable(splitter)
            except DataError:
                if not ignore_errors:
                    raise
                value = string[splitter.start:splitter.end]
            yield unic(value)
            string = string[splitter.end:]
            splitter = VariableSplitter(string)
        yield unescape(string)

    def _get_variable(self, splitter):
        if splitter.identifier not in '$@%':
            return self._get_reserved_variable(splitter)
        if splitter.index:
            return self._get_list_variable_item(splitter)
        return self._get_normal_variable(splitter)

    def _get_reserved_variable(self, splitter):
        value = splitter.get_replaced_variable(self)
        LOGGER.warn("Syntax '%s' is reserved for future use. Please "
                    "escape it like '\\%s'." % (value, value))
        return value

    def _get_normal_variable(self, splitter):
        name = splitter.get_replaced_variable(self)
        return self._variables[name]

    def _get_list_variable_item(self, splitter):
        name = splitter.get_replaced_variable(self)
        variable = self._variables[name]
        index = self.replace_string(splitter.index)
        try:
            index = int(index)
        except ValueError:
            raise DataError("List variable '%s' used with invalid index '%s'."
                            % (name, index))
        try:
            return variable[index]
        except IndexError:
            raise DataError("List variable '%s' has no item in index %d."
                            % (name, index))
