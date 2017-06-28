from zeit.brightcove.convert2 import Video as BCVideo
from zeit.content.video.video import Video as CMSVideo
import zeit.brightcove.testing
import zeit.cms.testing


class VideoTest(zeit.cms.testing.FunctionalTestCase,
                zeit.cms.tagging.testing.TaggingHelper):

    layer = zeit.brightcove.testing.ZCML_LAYER

    def test_converts_cms_fields_to_bc_names(self):
        cms = CMSVideo()
        cms.title = u'title'
        cms.teaserText = u'teaser'
        bc = BCVideo.from_cms(cms)
        self.assertEqual('title', bc.title)
        self.assertEqual('title', bc.data['name'])
        self.assertEqual('teaser', bc.teaserText)
        self.assertEqual('teaser', bc.data['description'])

    def test_setting_readonly_field_raises(self):
        bc = BCVideo()
        with self.assertRaises(AttributeError):
            bc.id = 'id'

    def test_missing_data_returns_field_default(self):
        bc = BCVideo()
        self.assertEqual(None, bc.ressort)

    def test_bc_names_with_slash_denote_nested_dict(self):
        cms = CMSVideo()
        cms.ressort = u'Deutschland'
        bc = BCVideo.from_cms(cms)
        self.assertEqual('Deutschland', bc.ressort)
        self.assertEqual('Deutschland', bc.data['custom_fields']['ressort'])

    def test_looks_up_type_conversion_by_field(self):
        cms = CMSVideo()
        cms.commentsAllowed = True
        bc = BCVideo.from_cms(cms)
        self.assertEqual(True, bc.commentsAllowed)
        self.assertEqual('1', bc.data['custom_fields']['allow_comments'])

    def test_converts_authors(self):
        from zeit.content.author.author import Author
        self.repository['a1'] = Author()
        self.repository['a2'] = Author()

        cms = CMSVideo()
        cms.authorships = (
            cms.authorships.create(self.repository['a1']),
            cms.authorships.create(self.repository['a2'])
        )
        bc = BCVideo.from_cms(cms)
        self.assertEqual(
            'http://xml.zeit.de/a1 http://xml.zeit.de/a2',
            bc.data['custom_fields']['authors'])
        self.assertEqual(
            (self.repository['a1'], self.repository['a2']), bc.authorships)

    def test_converts_keywords(self):
        cms = CMSVideo()
        self.setup_tags('staatsanwaltschaft', 'parlament')
        bc = BCVideo.from_cms(cms)
        self.assertEqual(
            'staatsanwaltschaft;parlament',
            bc.data['custom_fields']['cmskeywords'])
        self.assertEqual(cms.keywords, bc.keywords)

    def test_converts_product(self):
        cms = CMSVideo()
        cms.product = zeit.cms.content.sources.PRODUCT_SOURCE(None).find(
            'TEST')
        bc = BCVideo.from_cms(cms)
        self.assertEqual('TEST', bc.data['custom_fields']['produkt-id'])
        self.assertEqual(cms.product, bc.product)

    def test_product_defaults_to_reuters(self):
        bc = BCVideo()
        bc.data['reference_id'] = '1234'
        self.assertEqual('Reuters', bc.product.id)
