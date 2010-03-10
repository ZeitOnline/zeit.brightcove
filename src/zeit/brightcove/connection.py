# Copyright (c) 2010 gocept gmbh & co. kg
# Copyright (c) 2009 StudioNow, Inc <patrick@studionow.com>
# See also LICENSE.txt

import simplejson
import urllib
import urllib2
import zope.app.appsetup.product


class APIConnection(object):

    def __init__(self, read_token, write_token, read_url, write_url):
        self.read_token = read_token
        self.write_token = write_token
        self.read_url = read_url
        self.write_url = write_url


    def post(self, command, **kwargs):
        params = dict(
            (key, value) for key, value in kwargs.items() if key and value)
        params['token'] = self.write_token
        data = dict(method=command, params=params)
        post_data = urllib.urlencode(dict(json=simplejson.dumps(data)))
        request = urllib2.urlopen(self.write_url, post_data)
        response = simplejson.load(request)
        __traceback_info__ = (response, )
        error = response.get('error')
        if error:
            raise RuntimeError(error)
        return response['result']

    def get(self, command, **kwargs):
        url = '%s?%s' % (self.read_url, urllib.urlencode(dict(
            output='JSON',
            command=command,
            token=self.read_token,
            **kwargs)))
        request = urllib2.urlopen(url)
        response = simplejson.load(request)
        __traceback_info__ = (url, response)
        error = response.get('error')
        if error:
            raise RuntimeError(error)
        return response

    def get_list(self, command, item_class, **kwargs):
        return ItemResultSet(self, command, item_class, **kwargs)


class ItemResultSet(object):

    def __init__(self, connection, command, item_class, **kwargs):
        self.connection = connection
        self.command = command
        self.item_class = item_class
        self.data = kwargs

    def __iter__(self):
        page = 0
        while True:
            data = self.connection.get(self.command,
                                       page_size='100',
                                       page_number=str(page),
                                       get_item_count='true',
                                       **self.data)
            for item in data['items']:
                yield self.item_class(item)
            total_count = int(data['total_count'])
            page_number = int(data['page_number'])
            page_size = int(data['page_size'])
            if total_count < 0 or page_size == 0:
                # This doesn't seem right but is what happens when fetching a
                # list less than a single page
                break
            if not data:
                break
            page += 1


def connection_factory():
    config = zope.app.appsetup.product.getProductConfiguration(
        'zeit.brightcove')
    return APIConnection(
        config['read-token'],
        config['write-token'],
        config['read-url'],
        config['write-url'])