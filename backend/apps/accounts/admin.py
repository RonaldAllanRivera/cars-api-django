from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.utils.translation import ngettext

from apps.accounts.models import ApiToken, User


class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "name")

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("A user with that email address already exists.")
        return email


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A user with that email address already exists.")
        return email


class ApiTokenInline(admin.TabularInline):
    model = ApiToken
    extra = 0
    can_delete = False
    show_change_link = True
    fields = ("name", "abilities_display", "last_used_at", "expires_at", "created_at")
    readonly_fields = fields
    verbose_name_plural = "API tokens"

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Abilities")
    def abilities_display(self, obj):
        return ", ".join(obj.abilities or []) or "—"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreationForm
    list_display = ("email", "name", "is_staff", "is_superuser", "is_active", "last_login", "created_at")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email", "name")
    ordering = ("email",)
    readonly_fields = ("last_login", "created_at", "updated_at")
    filter_horizontal = ("groups", "user_permissions")
    inlines = [ApiTokenInline]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("name",)}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "usable_password", "password1", "password2", "is_staff", "is_active"),
            },
        ),
    )

    def get_inlines(self, request, obj):
        # Tokens only exist for saved users; the add page has nothing to show.
        return self.inlines if obj is not None else []


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    """Read-only view of issued tokens. The hash never leaves the database."""

    list_display = ("name", "user", "abilities_display", "last_used_at", "expires_at", "created_at")
    list_select_related = ("user",)
    list_filter = ("created_at", "last_used_at")
    search_fields = ("name", "user__email", "user__name")
    fields = ("name", "user", "abilities_display", "last_used_at", "expires_at", "created_at")
    readonly_fields = fields
    date_hierarchy = "created_at"
    actions = ["revoke_selected"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        # "Revoke" says what deleting a token means; a second, generic delete adds nothing.
        actions.pop("delete_selected", None)
        return actions

    @admin.display(description="Abilities")
    def abilities_display(self, obj):
        return ", ".join(obj.abilities or []) or "—"

    @admin.action(description="Revoke selected tokens", permissions=["delete"])
    def revoke_selected(self, request, queryset):
        revoked, _ = queryset.delete()
        self.message_user(
            request,
            ngettext("Revoked %d token.", "Revoked %d tokens.", revoked) % revoked,
            messages.SUCCESS,
        )
