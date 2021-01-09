# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext as __
from django.conf import settings
from django_mongodb_engine.contrib import MongoDBManager
from djangotoolbox.fields import ListField, EmbeddedModelField

from ikwen.core.models import Model, Service, AbstractWatchModel, AbstractConfig, Country
from ikwen.core.constants import STARTED
from ikwen.accesscontrol.models import Member

from ikwen.billing.models import AbstractSubscription
from ikwen.core.utils import to_dict

ADMIN_EMAIL = 'wilfriedwillend@gmail.com'
ECONNECT = 'eConnect'
NUMERIHOME = 'NUMERILINK Home'
NUMERIHOTEL = 'NUMERILINK Hotel'
HOME = 'HOMELINK'
OFFICE = 'OFFICELINK'
CORPORATE = 'CORPORATELINK'
RENTAL = "rental"
PURCHASE = "purchase"
REPORTED = "Reported"
CANCELED = "Canceled"
FINISHED = "Finished"
DEVICE_ID = "device_id"

ANALOG = 'Analog'
DIGITAL = 'Digital'
TYPE_CHOICES = (
    (ANALOG, 'Analog'),
    (DIGITAL, 'Digital')
)
EN = 'en'
FR = 'fr'
LANG_CHOICES = (
    (EN, 'English'),
    (FR, u'Français'),
)
MEDIA_DIR = getattr(settings, 'MEDIA_ROOT') + 'tiny_mce/'
TINYMCE_MEDIA_URL = getattr(settings, 'MEDIA_URL') + 'tiny_mce/'


class ModelI18n(Model):
    language = models.CharField(max_length=6, blank=True, null=True)

    class Meta:
        abstract = True


class Interactive(object):
    def _get_interaction_set(self):
        return Interaction.objects.filter(object_id=self.id)
    interaction_set = property(_get_interaction_set)


class Product(ModelI18n):
    UPLOAD_TO = 'econnect/'
    lang = models.CharField(max_length=10, choices=LANG_CHOICES, default=EN)
    name = models.CharField(max_length=200)
    slug = models.CharField(max_length=250)
    slogan = models.CharField(max_length=250)
    description = models.TextField(blank=True, null=True,
                                   help_text="Description appears below the banner on the product presentation page")
    catchy_title = models.CharField(max_length=250, help_text="Title for banner appear on product and pricing page")
    catchy = models.TextField(blank=True, null=True, help_text="Text for banner appear on product and pricing page")
    cta_label = models.CharField(max_length=30, verbose_name="Call-to-action")
    install_cost = models.IntegerField(default=0)
    logo = models.ImageField(blank=True, null=True, upload_to=UPLOAD_TO,
                             help_text="600 x 600px ; will appear on homepage")
    cover = models.ImageField(blank=True, null=True, upload_to=UPLOAD_TO,
                              help_text="1920 x 500px ; will appear on product banner")
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return self.name + ' | ' + self.lang


class Package(ModelI18n):
    product = models.ForeignKey(Product)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, blank=True, null=True)
    name = models.CharField(max_length=15)
    target = models.IntegerField(blank=True, null=True, default=1,
                                 help_text=_("Indicate the default number of targets corresponding to the offer.<br>"
                                             "Can be: <strong>PCs</strong>, <strong>TVs</strong>, etc."))
    optional_target_cost = models.IntegerField(blank=True, null=True, verbose_name="Optional target cost",
                                               help_text=_("Indicate the cost peer additional targets."))
    short_description = models.TextField(blank=True,
                                         help_text=_("Short description understandable by the customer."))
    description = models.TextField()
    summary = models.TextField()
    duration = models.IntegerField(default=30,
                                   help_text="Number of days covered by the cost this product.")
    duration_text = models.CharField(max_length=30, blank=True, null=True,
                                     help_text=_("How you want the customer to see the duration.<br>"
                                                 "Eg:<strong>1 month</strong>, <strong>3 months</strong>, etc."))
    cost = models.IntegerField()
    order_of_appearance = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __unicode__(self):
        if self.type:
            return "%s %s %s | %s" % (self.product.name, self.name, self.type, self.product.lang)
        else:
            return self.product.name + ' ' + self.name + ' | ' + self.product.lang

    def get_obj_details(self):
        return "%s XAF" % self.cost


class Equipment(ModelI18n):
    product = models.ForeignKey(Product)
    name = models.CharField(max_length=240)
    slug = models.SlugField(max_length=250)
    purchase_cost = models.IntegerField(default=0)
    rent_cost = models.IntegerField(default=0)
    is_purchased = models.BooleanField(default=True)
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return str(self.product) + ' | ' + self.name


class Extra(ModelI18n):
    product = models.ForeignKey(Product)
    name = models.CharField(max_length=240)
    slug = models.SlugField(max_length=250)
    cost = models.IntegerField(default=0)
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return str(self.product) + ' | ' + self.name


class AddOn(ModelI18n):
    product = models.ForeignKey(Product)
    equipment = models.ForeignKey(Equipment)
    extra = models.ForeignKey(Extra)


class EquipmentOrderEntry(Model):
    equipment = models.ForeignKey(Equipment)
    name = models.CharField(max_length=240)
    cost = models.IntegerField(default=0)
    is_rent = models.BooleanField(default=False)


class Order(Model, Interactive):
    member = models.ForeignKey(Member, related_name='+')
    package = models.ForeignKey(Package)
    equipment_order_entry_list = ListField(EmbeddedModelField('EquipmentOrderEntry'), editable=False)
    optional_tv = models.IntegerField(blank=True, null=True)
    extra_list = ListField(EmbeddedModelField('Extra'), editable=False, blank=True, null=True)
    location_lat = models.FloatField(default=0.0)
    location_lng = models.FloatField(default=0.0)
    maps_id = models.CharField(max_length=20, blank=True, null=True)
    formatted_address = models.CharField(max_length=250)
    cost = models.IntegerField(default=0)
    status = models.CharField(max_length=30, default=STARTED)
    tags = models.CharField(max_length=250)

    def _get_maps_url(self):
        return getattr(settings, 'CREOLINK_MAPS_URL') + \
               "equipments?device_id=%s&lat=%s&lng=%s" % (self.maps_id, self.location_lat, self.location_lng)
    maps_url = property(_get_maps_url)


class Faq(Model):
    product = models.ForeignKey(Product)
    question = models.TextField()
    answer = models.TextField()
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return self.question

    def get_obj_details(self):
        return self.product


class Advertisement(Model):
    UPLOAD_TO = 'econnect/'
    lang = models.CharField(max_length=10, choices=LANG_CHOICES, default=EN, verbose_name="Language")
    title = models.CharField(max_length=240)
    description = models.TextField()
    cta_label = models.CharField(max_length=30, verbose_name="Call-to-action")
    cta_url = models.URLField(verbose_name="Call-to-action URL")
    image = models.ImageField(blank=True, null=True, upload_to=UPLOAD_TO,
                              help_text="500 x 500px ; will appear on homepage")
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return self.title

    def get_obj_details(self):
        return self.description


class Subscription(AbstractSubscription):
    order = models.ForeignKey(Order, blank=True, null=True)


class Site(Model):
    member = models.ForeignKey(Member, related_name='+', blank=True, null=True)
    package = models.ForeignKey(Package, verbose_name=_("Subscription"))
    subscription = models.ForeignKey(Subscription, blank=True, null=True)
    code = models.CharField(_("Site Code"), max_length=30)
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return str(self.package)

    def get_obj_details(self):
        return "Code Site : " + str(self.code) + "<br />" +\
               "Expires on : " + str(self.subscription.expiry)


class Profile(Model):
    member = models.ForeignKey(Member, related_name='+', blank=True, null=True)
    code = models.CharField(_("Client Code"), max_length=15)
    country = models.ForeignKey(Country, verbose_name=_("Country"), blank=True, null=True)
    city = models.CharField(_("City"), max_length=30, blank=True, null=True)
    district = models.CharField(_("Neighborhood"), max_length=30, blank=True, null=True)
    code_update_count = models.IntegerField(default=0,
                                            help_text="Counts how many times the code was updated. User should not be "
                                                      "allowed to modify more than twice.")

    def __unicode__(self):
        return self.code

    def get_obj_details(self):
        return self.city


class CustomerRequest(Model):
    member = models.ForeignKey(Member, related_name='+')
    name = models.CharField(max_length=250)
    label = models.CharField(max_length=250, blank=False, null=False)


class IncompleteClient(Model, Interactive):
    """
    Represents a client imported from Navision without email.
    When a client does not have email, the corresponding Member
    object cannot be created. A list of such clients is built
    for the Call-Center to revive them one by one and get them to provide their emails
    """
    code = models.CharField(max_length=15, unique=True)
    name = models.CharField(max_length=100, db_index=True)
    city = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    email = models.EmailField(blank=True, null=True, db_index=True,
                              help_text="The email is empty when the object is created and manually set "
                                        "later when we obtain it. A cron will traverse objects having "
                                        "email set and create the corresponding Member")
    phone = models.CharField(max_length=60, blank=True, null=True, db_index=True)
    last_access = models.DateTimeField(blank=True, null=True, db_index=True,
                                       help_text="Last time this client file was accessed, probably for a revival "
                                                 "by the Call-Center")

    def __unicode__(self):
        return self.name

    def get_obj_details(self):
        last_access = self.last_access.strftime('%Y-%m-%d %H:%M') if self.last_access else '---'
        return __("<span><strong>Client Code:</strong> %(client_code)s</span>&nbsp;&nbsp;"
                  "<span><strong>Last access:</strong> "
                  "%(last_access)s</span>" % {'client_code': self.code, 'last_access': last_access})


class Interaction(Model):
    """
    Any interaction done by a Staff on either an Order or
    an IncompleteClient. This allows to monitor how those
    have been addressed.
    """
    CALL = 'Call'
    TEXT = 'Text'
    EMAIL = 'Email'
    INTERVENTION = 'Intervention'

    INTERACTION_TYPES = (
        (CALL, _('Call')),
        (TEXT, _('Text / WhatsApp')),
        (EMAIL, _('Email')),
        (INTERVENTION, _('Intervention'))
    )
    member = models.ForeignKey(Member)
    object_id = models.CharField(max_length=24, db_index=True)  # ID of Order or IncompleteClient
    type = models.CharField(max_length=100, choices=INTERACTION_TYPES, db_index=True)
    summary = models.TextField(blank=True, null=True)
    response = models.TextField()
    next_rdv = models.DateTimeField(blank=True, null=True)
    viewed_by = ListField()  # List of sudo who already checked this interaction

    objects = MongoDBManager()

    def to_dict(self):
        val = to_dict(self)
        val['member'] = self.member.full_name
        return val


class Config(AbstractConfig):
    payment_delay = models.IntegerField(default=15)
    notification_email = models.CharField(max_length=250,
                                          help_text="Set which mailbox should be notified when "
                                                    "an order is submit, separate with ','")
