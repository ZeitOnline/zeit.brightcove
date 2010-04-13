# Copyright (c) 2010 gocept gmbh & co. kg
# See also LICENSE.txt

from zeit.cms.i18n import MessageFactory as _
import datetime
import grokcore.component
import persistent
import persistent.mapping
import pytz
import transaction
import zeit.brightcove.interfaces
import zeit.cms.browser.interfaces
import zeit.cms.content.interfaces
import zeit.cms.content.interfaces
import zeit.cms.interfaces
import zeit.cms.type
import zeit.cms.workflow.interfaces
import zope.component
import zope.container.contained
import zope.dublincore.interfaces
import zope.interface



class mapped(object):

    def __init__(self, *path):
        assert path
        self.path = path

    def __get__(self, instance, class_):
        if instance is None:
            return self
        return self._get_from_dict(instance.data)

    def _get_from_dict(self, value):
        for key in self.path:
            value = value.get(key)
            if value is None:
                break
        return value

    def __set__(self, instance, value):
        data = instance.data
        for key in self.path[:-1]:
            data = data.setdefault(key, persistent.mapping.PersistentMapping())
        data[self.path[-1]] = value
        instance.save_to_brightcove()


class mapped_bool(mapped):

    def __get__(self, instance, class_):
        value = super(mapped_bool, self).__get__(instance, class_)
        return value == '1'

    def __set__(self, instance, value):
        value = '1' if value else '0'
        super(mapped_bool, self).__set__(instance, value)


class mapped_keywords(mapped):

    def __get__(self, instance, class_):
        value = super(mapped_keywords, self).__get__(instance, class_)
        if value:
            keywords = zope.component.getUtility(
                zeit.cms.content.interfaces.IKeywords)
            value = value.split(';')
            return tuple(keywords[code] for code in value if code in keywords)
        return ()

    def __set__(self, instance, value):
        if value:
            value = ';'.join(keyword.code for keyword in value)
        super(mapped_keywords, self).__set__(instance, value)


class Content(persistent.Persistent,
            zope.container.contained.Contained):

    zope.interface.implements(zeit.brightcove.interfaces.IBrightcoveContent)

    data = None
    id = mapped('id')
    title = mapped('name')
    teaserText = mapped('shortDescription')
    brightcove_thumbnail = mapped('thumbnailURL')

    def __init__(self, data, connection=None):
        if data is not None:
            self.data = persistent.mapping.PersistentMapping(data)
            if 'customFields' in self.data:
                self.data['customFields'] = (
                    persistent.mapping.PersistentMapping(
                        self.data['customFields']))
            self.uniqueId = 'http://video.zeit.de/%s/%s' % (self.type, self.data['id'])

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.__name__ == other.__name__

    @property
    def __parent__(self):
        return zope.component.getUtility(
            zeit.brightcove.interfaces.IRepository)

    @__parent__.setter
    def __parent__(self, value):
        if self.__parent__ != value:
            raise ValueError(value)

    @property
    def __name__(self):
        return '%s:%s' % (self.type, self.data['id'])

    @property
    def thumbnail(self):
        return self.data['thumbnailURL']

    @staticmethod
    def get_connection():
        return zope.component.getUtility(
            zeit.brightcove.interfaces.IAPIConnection)

    def save_to_brightcove(self):
        registered = getattr(self, '_v_save_hook_registered', False)
        if not registered:
            transaction.get().addBeforeCommitHook(self._save)
            self.__parent__[self.__name__] = self
            self._v_save_hook_registered = True

    def _save(self):
        try:
            del self._v_save_hook_registered
        except AttribueError:
            pass
        __traceback_info__ = (self.data,)
        data = dict(self.data)
        if 'customFields' in data:
            data['customFields'] = dict(data['customFields'])
        self.get_connection().post('update_video', video=data)


class Video(Content):

    zope.interface.implements(zeit.brightcove.interfaces.IVideo)
    type = 'video'
    allow_comments = mapped_bool('customFields', 'allow_comments')
    banner = mapped_bool('customFields', 'banner')
    banner_id = mapped('customFields', 'banner-id')
    breaking_news = mapped_bool('customFields', 'breaking-news')
    dailyNewsletter = mapped_bool('customFields', 'newsletter')
    has_recensions = mapped_bool('customFields', 'recensions')
    item_state = mapped('itemState')
    keywords = mapped_keywords('customFields', 'cmskeywords')
    product_id = mapped('customFields', 'produkt-id')
    ressort = mapped('customFields', 'ressort')
    serie = mapped('customFields', 'serie')
    subtitle = mapped('longDescription')
    supertitle = mapped('customFields', 'supertitle')
    video_still = mapped('videoStillURL')


    fields = ",".join((
        'creationDate',
        'customFields',
        'economics',
        'endDate',
        'id',
        'itemState',
        'lastModifiedDate',
        'length',
        'linkText',
        'linkURL',
        'longDescription',
        'name',
        'playsTotal',
        'playsTrailingWeek',
        'publisheddate',
        'referenceId',
        'shortDescription',
        'tags',
        'thumbnailURL',
        'videoStillURL',
    ))

    @classmethod
    def find_by_ids(class_, ids):
        ids = ','.join(str(i) for i in ids)
        return class_.get_connection().get_list(
            'find_videos_by_ids', class_, video_ids=ids,
            video_fields=class_.fields)

    @classmethod
    def find_modified(class_, from_date):
        from_date = int(from_date.strftime("%s")) / 60
        # PLAYABLE,INACTIVE,DELETED,UNSCHEDULED
        return class_.get_connection().get_list(
            'find_modified_videos', class_,
            from_date=from_date,
            video_fields=class_.fields,
            filter="PLAYABLE,DELETED,INACTIVE,UNSCHEDULED")

    @property
    def related(self):
        result = []
        custom = self.data.get('customFields')
        if custom is None:
            return ()
        for i in range(1, 6):
            unique_id = custom.get('ref_link%s' % i)
            if unique_id is not None:
                content = zeit.cms.interfaces.ICMSContent(unique_id, None)
                if content is not None:
                    result.append(content)
        return tuple(result)
    
    def __create_bc_date__(self, ts):
        date = datetime.datetime.utcfromtimestamp(ts/1000)
        return pytz.utc.localize(date)


    @property
    def expires(self):
        ts = self.data.get('endDate')
        if not ts: return None
        return self.__create_bc_date__(int(ts)) 
       
    @property
    def date_last_modified (self):
        ts = self.data.get('lastModifiedDate')
        if not ts: return None
        return self.__create_bc_date__(int(ts)) 
    
    @property
    def date_created(self):
        ts = self.data.get('creationDate')
        if not ts: return None
        return self.__create_bc_date__(int(ts)) 

    @property
    def date_first_released(self):
        ts = self.data.get('publishedDate')
        if not ts: return None
        return self.__create_bc_date__(int(ts)) 

    @related.setter
    def related(self, value):
        if not value:
            value = ()
        custom = self.data.setdefault('customFields',
                                      persistent.mapping.PersistentMapping())
        for i in range(1, 6):
            custom.pop('ref_link%i' % i, None)
            custom.pop('ref_title%i' % i, None)
        for i, obj in enumerate(value, 1):
            metadata  = zeit.cms.content.interfaces.ICommonMetadata(obj, None)
            if metadata is None:
                continue
            custom['ref_link%s' % i] = obj.uniqueId
            custom['ref_title%s' % i] = metadata.teaserTitle


class BrightcoveContentPublicationStatus(grokcore.component.Adapter):

    grokcore.component.context(zeit.brightcove.interfaces.IBrightcoveContent)
    grokcore.component.implements(
        zeit.cms.workflow.interfaces.IPublicationStatus)

    @property
    def published(self):
        if self.context.item_state == "ACTIVE":
            return "published"
        return "not-published"


class VideoType(zeit.cms.type.TypeDeclaration):

    title = _('Video')
    interface = zeit.brightcove.interfaces.IVideo


class Playlist(Content):

    zope.interface.implements(zeit.brightcove.interfaces.IPlaylist)
    type = 'playlist'
    item_state = 'ACTIVE'
    fields = ",".join((
        'id',
        'name',
        'shortDescription',
        'thumbnailURL',
        'videoIds',
    ))

    @classmethod
    def find_by_ids(class_, ids):
        ids = ','.join(str(i) for i in ids)
        return class_.get_connection().get_list(
            'find_playlists_by_ids', class_,
            playlist_fields=class_.fields,
            playlist_ids=ids)

    @classmethod
    def find_all(class_):
        return class_.get_connection().get_list(
            'find_all_playlists', class_,
            playlist_fields=class_.fields)


class PlaylistType(zeit.cms.type.TypeDeclaration):

    title = _('Playlist')
    interface = zeit.brightcove.interfaces.IPlaylist


@grokcore.component.adapter(basestring,
                            name='http://video.zeit.de/')
@grokcore.component.implementer(zeit.cms.interfaces.ICMSContent)
def unique_id_to_cms_content(uniqueId):
    assert uniqueId.startswith('http://video.zeit.de/')
    name = uniqueId.replace('http://video.zeit.de/', '', 1)
    name = name.replace('/', ':', 1)
    repository = zope.component.getUtility(
        zeit.brightcove.interfaces.IRepository)
    try:
        return repository[name]
    except KeyError:
        return None


class UUID(grokcore.component.Adapter):

    grokcore.component.context(zeit.brightcove.interfaces.IBrightcoveContent)
    grokcore.component.implements(zeit.cms.content.interfaces.IUUID)

    @property
    def id(self):
        return self.context.uniqueId


class PublishInfo(grokcore.component.Adapter):
    grokcore.component.context(zeit.brightcove.interfaces.IVideo)
    grokcore.component.implements(zeit.cms.workflow.interfaces.IPublishInfo)

    @property
    def date_first_released(self):
        return self.context.date_first_released


class Modified(grokcore.component.Adapter):
    grokcore.component.context(zeit.brightcove.interfaces.IVideo)
    grokcore.component.implements(zeit.cms.workflow.interfaces.IModified)

    @property
    def date_last_modified(self):
        return self.context.date_last_modified


class IDCPublishing(grokcore.component.Adapter):
    grokcore.component.context(zeit.brightcove.interfaces.IVideo)
    grokcore.component.implements(zope.dublincore.interfaces.IDCPublishing)

    @property
    def effective(self):
        return None

    @property
    def expires(self):
        return self.context.expires


class IDCTimes(grokcore.component.Adapter):
    grokcore.component.context(zeit.brightcove.interfaces.IVideo)
    grokcore.component.implements(zope.dublincore.interfaces.IDCTimes)

    @property
    def created(self):
        return self.context.date_created

    @property
    def modified(self):
        return self.context.date_last_modified


class CommonMetadata(grokcore.component.Adapter):

    grokcore.component.context(zeit.brightcove.interfaces.IBrightcoveContent)
    grokcore.component.implements(zeit.cms.content.interfaces.ICommonMetadata)

    @property
    def year(self):
        try:
            modified = int(self.context.data.get('lastModifiedDate'))
        except (TypeError, ValueError):
            return None
        return datetime.datetime.fromtimestamp(modified/1000).year

    @property
    def teaserTitle(self):
        return self.title

    def __getattr__(self, key):
        if key in zeit.cms.content.interfaces.ICommonMetadata:
            return getattr(self.context, key, None)
        return super(CommonMetadata, self).__getattr__(key)


class CommonMetadataVideo(CommonMetadata):
    grokcore.component.context(zeit.brightcove.interfaces.IVideo)
    
    @property 
    def commentsAllowed(self):
        return self.context.allow_comments


@grokcore.component.adapter(
    zeit.brightcove.interfaces.IBrightcoveContent,
    zeit.cms.browser.interfaces.ICMSSkin)
@grokcore.component.implementer(
    zeit.cms.browser.interfaces.IListRepresentation)
def list_repr(context, request):
    metadata = zeit.cms.content.interfaces.ICommonMetadata(context)
    return zope.component.queryMultiAdapter(
        (metadata, request),
        zeit.cms.browser.interfaces.IListRepresentation)

