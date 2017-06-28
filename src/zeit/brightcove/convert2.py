from zeit.content.video.interfaces import IVideo
from zope.cachedescriptors.property import Lazy as cachedproperty
import grokcore.component as grok
import zeit.cms.interfaces
import zope.interface
import zope.schema


class dictproperty(object):
    """Maps a property from a CMS name to a BC name, and performs type
    conversion, using an associated CMS schema field."""

    # Might be cleaner if we figured this out by ourselves, but that would be
    # mechanically finicky and doesn't seem worth the hassle. So we simply have
    # Video.properties set it for us instead.
    __name__ = None

    def __init__(self, bc_name, field, converter=None):
        """The value is stored in the instance's data dict, under the key
        ``bc_name`` (may contain '/' to denote nested dicts).

        You can pass the class name of an ITypeConverter (to prevent source
        code ordering / import time issues), otherwise one will be looked up
        for the given field.
        """
        self.bc_name = bc_name
        segments = self.bc_name.split('/')
        self.path = segments[:-1]
        self.name = segments[-1]
        self.field = field
        self._converter = converter

    def __get__(self, instance, cls):
        if instance is None:
            return self
        data = instance.data
        for x in self.path:
            data = data.get(x, {})
        try:
            value = data[self.name]
        except KeyError:
            return self.field.default
        return self.converter.to_cms(value)

    def __set__(self, instance, value):
        if self.field.readonly:
            raise AttributeError('Cannot set %s', self.bc_name)
        data = instance.data
        for x in self.path:
            data = data.setdefault(x, {})
        data[self.name] = self.converter.to_bc(value)

    @cachedproperty
    def converter(self):
        if self._converter is None:
            return ITypeConverter(self.field)
        else:
            return globals()[self._converter](self.field)


class Video(object):
    """Converts video data between CMS and Brightcove.

    * Stores json data received from the Brightcove API in a nested dict
    * Presents it as properties with CMS names and with CMS types for reading
    * On write, those properties convert to BC names and BC types

    Can be constructed from both a CMS object and a BC API result dict.
    """

    id = dictproperty('id', zope.schema.TextLine(readonly=True))
    title = dictproperty('name', IVideo['title'])
    teaserText = dictproperty('description', IVideo['teaserText'])

    authorships = dictproperty('custom_fields/authors', IVideo['authorships'],
                               'AuthorshipsConverter')
    commentsAllowed = dictproperty(
        'custom_fields/allow_comments', IVideo['commentsAllowed'])
    ressort = dictproperty('custom_fields/ressort', IVideo['ressort'])

    def __init__(self):
        self.data = {}

    @classmethod
    def from_cms(cls, video):
        instance = cls()
        instance.data['id'] = video.brightcove_id
        for prop in instance.properties:
            if prop.field.readonly:
                continue
            setattr(instance, prop.__name__, prop.field.get(video))
        return instance

    @property
    def properties(self):
        cls = type(self)
        result = []
        for propname in dir(cls):
            prop = getattr(cls, propname)
            if not isinstance(prop, dictproperty):
                continue
            prop.__name__ = propname
            result.append(prop)
        return result

    def __repr__(self):
        return '<%s.%s %s>' % (
            self.__class__.__module__, self.__class__.__name__,
            self.id or '(unknown)')


class ITypeConverter(zope.interface.Interface):

    def to_bc(value):
        pass

    def to_cms(value):
        pass


class Converter(grok.Adapter):

    grok.baseclass()
    grok.implements(ITypeConverter)

    def to_bc(self, value):
        return value

    def to_cms(self, value):
        return value


class DefaultPassthroughConverter(Converter):

    grok.context(zope.interface.Interface)


class BoolConverter(Converter):

    grok.context(zope.schema.Bool)

    def to_bc(self, value):
        return '1' if value else '0'

    def to_cms(self, value):
        return value == '1'


class AuthorshipsConverter(Converter):

    # used explicitly, since we cannot register an adapter for a field instance
    grok.baseclass()

    SEPARATOR = u' '

    def to_bc(self, value):
        return self.SEPARATOR.join(x.target.uniqueId for x in value)

    def to_cms(self, value):
        if not value:
            return ()
        authors = [zeit.cms.interfaces.ICMSContent(x, None)
                   for x in value.split(self.SEPARATOR)]
        return tuple([x for x in authors if x is not None])
