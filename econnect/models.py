from django.db import models
from django.utils.translation import gettext_lazy as _
from djangotoolbox.fields import ListField, EmbeddedModelField

from ikwen.core.models import Model, Service, AbstractWatchModel, AbstractConfig
from ikwen.core.constants import STARTED
from ikwen.accesscontrol.models import Member

from ikwen.billing.models import AbstractSubscription

ECONNECT = 'econnect'
NUMERIHOME = 'NumeriLink Home'
NUMERIHOTEL = 'NumeriLink Hotel'
HOME = 'HomeLink'
OFFICE = 'OfficeLink'
CORPORATE = 'CorporateLink'
RENTAL = "rental"
PURCHASE = "purchase"
REPORTED = "Reported"
FINISHED = "Finished"
DEVICE_ID = "device_id"

ANALOG = 'Analog'
DIGITAL = 'Digital'
TYPE_CHOICES = (
    (ANALOG, 'Analog'),
    (DIGITAL, 'Digital')
)


class ModelI18n(Model):
    language = models.CharField(max_length=6, blank=True, null=True)

    class Meta:
        abstract = True


class Product(ModelI18n):
    UPLOAD_TO = 'econnect/'
    name = models.CharField(max_length=200)
    slug = models.CharField(max_length=250)
    summary = models.CharField(max_length=250)
    description = models.TextField(blank=True, null=True)
    cta_label = models.CharField(max_length=30, verbose_name="Call-to-action")
    install_cost = models.IntegerField(default=0)
    logo = models.ImageField(blank=True, null=True, upload_to=UPLOAD_TO,
                             help_text="150 x 150px")
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return self.name


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
    duration = models.IntegerField(default=30,
                                   help_text="Number of days covered by the cost this product.")
    duration_text = models.CharField(max_length=30, blank=True, null=True,
                                     help_text=_("How you want the customer to see the duration.<br>"
                                                 "Eg:<strong>1 month</strong>, <strong>3 months</strong>, etc."))
    cost = models.IntegerField()
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        if self.type:
            return "%s %s %s" % (self.product, self.name, self.type)
        else:
            return str(self.product) + ' ' + self.name

    def get_obj_details(self):
        return "%s | %s" % (self.description, self.cost)


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


class Order(Model):
    member = models.ForeignKey(Member, related_name='+')
    package = models.ForeignKey(Package)
    equipment_order_entry_list = ListField(EmbeddedModelField('EquipmentOrderEntry'), editable=False)
    optional_tv = models.IntegerField(blank=True, null=True)
    extra_list = ListField(EmbeddedModelField('Extra'), editable=False, blank=True, null=True)
    location_lat = models.FloatField(default=0.0)
    location_lng = models.FloatField(default=0.0)
    maps_url = models.URLField(blank=True, null=True)
    maps_id = models.CharField(max_length=20, blank=True, null=True)
    formatted_address = models.CharField(max_length=250)
    cost = models.IntegerField(default=0)
    status = models.CharField(max_length=30, default=STARTED)


class CustomerRequest(Model):
    member = models.ForeignKey(Member, related_name='+')
    name = models.CharField(max_length=250)
    label = models.CharField(max_length=250, blank=False, null=False)


class Subscription(AbstractSubscription):
    order = models.ForeignKey(Order)


class Config(AbstractConfig):
    payment_delay = models.IntegerField(default=15)
