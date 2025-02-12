from django.contrib import admin
from django.contrib.admin import AdminSite

from rest_framework.authtoken.models import Token
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import User, Group


class AssistantAdminSite(AdminSite):
    # Text to put at the end of each page's <title>.
    site_title = "Bots admin"

    # Text to put in each page's <h1> (and above login form).
    site_header = "Bots admin"

    # Text to put at the top of the admin index page.
    index_title = ""


class TokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'created')
    readonly_fields = ('key', 'created')


class SuperUserMixin:

    def has_module_permission(self, request):
        # Only superuser can see this model in the admin interface
        return request.user.is_superuser

#
# admin_site = AssistantAdminSite()
# admin_site.register(User, UserAdmin)
# admin_site.register(Group, GroupAdmin)
# admin_site.register(Token, TokenAdmin)
