import logging
from typing import Iterable, List, Optional, Tuple

from django.contrib import admin
from django.db.models import F
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from django.template.defaultfilters import truncatechars
from django.utils.safestring import mark_safe

from .models import PackageVersion

logger = logging.getLogger(__name__)


def html_list(data: Optional[Iterable]) -> str:
    """Convert dict into formatted HTML."""
    if data is None:
        return ""

    def as_li(val: str) -> str:
        return f"<li>{val}</li>"

    items = [as_li(v) for v in data]
    return mark_safe("<ul>%s</ul>" % "".join(items))


def check_pypi(
    modeladmin: admin.ModelAdmin, request: HttpRequest, queryset: QuerySet
) -> None:
    """Update latest package info from PyPI."""
    for p in queryset:
        if p.is_editable:
            logger.debug("Ignoring version update '%s' is editable", p.package_name)
        else:
            p.update_from_pypi()


check_pypi.short_description = "Update selected packages from PyPI"  # type: ignore


class UpdateAvailableListFilter(admin.SimpleListFilter):
    """Enable filtering by packages with an update available."""

    title = "Update available"
    parameter_name = "update"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> List[Tuple[str, str]]:
        return [
            ("1", "Yes"),
            ("0", "No"),
            ("-1", "Unknown"),
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        """Filter based on whether an update (of any sort) is available."""
        if self.value() == "-1":
            return queryset.filter(latest_version__isnull=True)
        elif self.value() == "0":
            return queryset.filter(
                current_version__isnull=False,
                latest_version__isnull=False,
                latest_version=F("current_version"),
            )
        elif self.value() == "1":
            return queryset.filter(
                current_version__isnull=False, latest_version__isnull=False
            ).exclude(latest_version=F("current_version"))
        else:
            return queryset


class PackageVersionAdmin(admin.ModelAdmin):

    actions = (check_pypi,)
    change_list_template = "change_list.html"
    list_display = (
        "package_name",
        "_updateable",
        "current_version",
        "next_version",
        "latest_version",
        "supports_py3",
        "_licence",
        "diff_status",
        "checked_pypi_at",
    )
    list_filter = (
        "diff_status",
        "is_editable",
        "is_parseable",
        UpdateAvailableListFilter,
        "supports_py3",
    )
    ordering = ["package_name"]
    readonly_fields = (
        "package_name",
        "is_editable",
        "is_parseable",
        "current_version",
        "next_version",
        "latest_version",
        "diff_status",
        "checked_pypi_at",
        "url",
        "licence",
        "raw",
        "available_updates",
        "python_support",
        "supports_py3",
        "django_support",
    )

    def _licence(self, obj: "PackageVersion") -> str:
        """Return truncated version of licence."""
        return truncatechars(obj.licence, 20)

    _licence.short_description = "PyPI licence"  # type: ignore

    def _updateable(self, obj: "PackageVersion") -> Optional[bool]:
        """Return True if there are available updates."""
        if obj.latest_version is None or obj.is_editable:
            return None
        else:
            return obj.latest_version != obj.current_version

    _updateable.boolean = True  # type: ignore
    _updateable.short_description = "Update available"  # type: ignore

    def available_updates(self, obj: "PackageVersion") -> str:
        """Print out all versions ahead of the current one."""
        from package_monitor import pypi

        package = pypi.Package(obj.package_name)
        versions = package.all_versions()
        return html_list([v for v in versions if v > obj.current_version])


admin.site.register(PackageVersion, PackageVersionAdmin)
