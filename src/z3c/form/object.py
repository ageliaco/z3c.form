##############################################################################
#
# Copyright (c) 2007 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
"""ObjectWidget related classes

$Id$
"""
__docformat__ = "reStructuredText"
import zope.i18n.format
import zope.interface
import zope.component
import zope.schema

from z3c.form.converter import BaseDataConverter

from z3c.form import form, interfaces, util
from z3c.form.field import Fields
from z3c.form.error import MultipleErrors
from z3c.form.i18n import MessageFactory as _

class ObjectSubForm(form.BaseForm):
    zope.interface.implements(interfaces.ISubForm)

    def __init__(self, context, parentWidget):
        self.context = context
        self.request = parentWidget.request
        self.__parent__ = parentWidget
        self.parentForm = parentWidget.form

    def _validate(self):
        for widget in self.widgets.values():
            try:
                # convert widget value to field value
                converter = interfaces.IDataConverter(widget)
                value = converter.toFieldValue(widget.value)
                # validate field value
                zope.component.getMultiAdapter(
                    (self.context,
                     self.request,
                     self.parentForm,
                     getattr(widget, 'field', None),
                     widget),
                    interfaces.IValidator).validate(value)
            except (zope.schema.ValidationError, ValueError), error:
                # on exception, setup the widget error message
                view = zope.component.getMultiAdapter(
                    (error, self.request, widget, widget.field,
                     self.parentForm, self.context),
                    interfaces.IErrorViewSnippet)
                view.update()
                widget.error = view

    def update(self, ignoreContext=None):
        self.fields = Fields(self.__parent__.field.schema)

        #update stuff from parent to be sure
        self.mode = self.__parent__.mode
        if ignoreContext is not None:
            self.ignoreContext = ignoreContext
        else:
            self.ignoreContext = self.__parent__.ignoreContext
        self.ignoreRequest = self.__parent__.ignoreRequest
        if interfaces.IFormAware.providedBy(self.__parent__):
            self.ignoreReadonly = self.parentForm.ignoreReadonly

        prefix = ''
        if self.parentForm:
            prefix = util.expandPrefix(self.parentForm.prefix) + \
                util.expandPrefix(self.parentForm.widgets.prefix)

        self.prefix = prefix+self.__parent__.field.__name__

        super(ObjectSubForm, self).update()

        self._validate()


class ObjectConverter(BaseDataConverter):
    """Data converter for IObjectWidget."""

    zope.component.adapts(
        zope.schema.interfaces.IObject, interfaces.IObjectWidget)

    factory = None

    def _fields(self):
        return zope.schema.getFields(self.field.schema)

    def toWidgetValue(self, value):
        """Just dispatch it."""
        if value is self.field.missing_value:
            return None

        return value

    def createObject(self, value):
        #keep value passed, maybe some subclasses want it
        #nasty: value here is the raw extracted from the widget's subform
        #in the form of (value-dict, (error1, error2))

        if self.factory is None:
            name = self.field.schema.__module__+'.'+self.field.schema.__name__
            creator = zope.component.queryMultiAdapter(
                (self.widget.context, self.widget.request,
                 self.widget.form, self.widget),
                interfaces.IObjectFactory,
                name=name)
            if creator:
                obj = creator(value)
            else:
                raise ValueError("No IObjectFactory adapter registered for %s" %
                                 name)
        else:
            #this is creepy, do we need this?
            #there seems to be no way to dispatch???
            obj = self.factory()

        return obj

    def toFieldValue(self, value):
        """See interfaces.IDataConverter"""
        if value is interfaces.NOVALUE:
            return self.field.missing_value

        if value[1]:
            raise MultipleErrors(value[1])

        if (self.widget._value is not interfaces.NOVALUE
            and not self.widget.subform.ignoreContext):
            obj = self.widget._value
        else:
            obj = self.createObject(value)

        obj = self.field.schema(obj)

        for name, f in self._fields().items():
            setattr(obj, name, value[0][name])
        return obj

class FactoryAdapter(object):
    """Most basic-default factory adapter"""

    zope.interface.implements(interfaces.IObjectFactory)
    zope.component.adapts(zope.interface.Interface, interfaces.IFormLayer,
        interfaces.IForm, interfaces.IWidget)

    factory = None

    def __init__(self, context, request, form, widget):
        self.context = context
        self.request = request
        self.form = form
        self.widget = widget

    def __call__(self, value):
        #value is the extracted data from the form
        return self.factory()

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.__name__)

# XXX: Probably we should offer an register factrory method which allows to
# use all discriminators e.g. context, request, form, widget as optional
# arguments. But can probably do that later in a ZCML directive
def registerFactoryAdapter(for_, klass):
    """register the basic FactoryAdapter for a given interface and class"""
    name = for_.__module__+'.'+for_.__name__
    class temp(FactoryAdapter):
        factory = klass
    zope.component.provideAdapter(temp, name=name)