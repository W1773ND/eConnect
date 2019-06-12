from django.db import models
from django.utils.translation import gettext_lazy as _
from djangotoolbox.fields import ListField, EmbeddedModelField

from ikwen.core.models import Model, Service, AbstractWatchModel
from ikwen.core.constants import PENDING_FOR_PAYMENT
from ikwen.accesscontrol.models import Member

NUMERI = 'NumeriLink'
HOME = 'HomeLink'
OFFICE = 'OfficeLink'
CORPORATE = 'CorporateLink'
RENTAL = "rental"
PURCHASE = "purchase"
OPTIONAL_TV_COST = 2500


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
    name = models.CharField(max_length=5)
    description = models.TextField()
    cost = models.IntegerField()
    order_of_appearance = models.IntegerField(default=0)

    def __unicode__(self):
        return str(self.product) + ' ' + self.name

    def get_obj_details(self):
        return "%s | %s" % (self.description, self.cost)


class Equipment (ModelI18n):
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
    formatted_address = models.CharField(max_length=250)
    cost = models.IntegerField(default=0)
    is_confirm = models.BooleanField(default=False)
    status = models.CharField(max_length=30, default=PENDING_FOR_PAYMENT)


class CustomerRequest(Model):
    member = models.ForeignKey(Member, related_name='+')
    name = models.CharField(max_length=250)
    label = models.CharField(max_length=250, blank=False, null=False)

