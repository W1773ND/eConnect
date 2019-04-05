from django.contrib import admin


class ProductAdmin(admin.ModelAdmin):
    fields = ('name', 'summary', 'description', )


class PackageAdmin(admin.ModelAdmin):
    fields = ('product', 'name', 'description', 'cost',)


class AddOnAdmin(admin.ModelAdmin):
    fields = ('product', 'name', 'type', 'description', 'cost', 'is_cyclic',)

