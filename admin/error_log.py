import json
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from unfold.decorators import action, display
from unfold.admin.filters import (
    DropdownFilter, 
    RangeDateFilter,
    MultipleSelectFieldListFilter,
    ChoicesDropdownFilter
)
from superapp.apps.admin_portal.admin import SuperAppModelAdmin
from superapp.apps.admin_portal.sites import superapp_admin_site
from superapp.apps.error_tracking.models import ErrorLog, ErrorLevel

User = get_user_model()


class ErrorLevelDropdownFilter(DropdownFilter):
    title = _('Error Level')
    parameter_name = 'error_level'
    
    def lookups(self, request, model_admin):
        return ErrorLevel.choices


class ResolvedStatusDropdownFilter(DropdownFilter):
    title = _('Status')
    parameter_name = 'resolved'
    
    def lookups(self, request, model_admin):
        return [
            ('0', _('Unresolved')),
            ('1', _('Resolved')),
        ]


class UserDropdownFilter(DropdownFilter):
    title = _('User')
    parameter_name = 'user'
    
    def lookups(self, request, model_admin):
        users = User.objects.filter(errorlog__isnull=False).distinct().values_list('id', 'username')[:100]
        return [(user_id, username) for user_id, username in users]


class ExceptionTypeDropdownFilter(DropdownFilter):
    title = _('Exception Type')
    parameter_name = 'exception_type'
    
    def lookups(self, request, model_admin):
        exception_types = ErrorLog.objects.values_list('exception_type', flat=True).distinct()[:50]
        return [(exc_type, exc_type) for exc_type in exception_types if exc_type]


class RecentErrorsFilter(admin.SimpleListFilter):
    title = _('Recent Errors')
    parameter_name = 'recent'
    
    def lookups(self, request, model_admin):
        return [
            ('1h', _('Last Hour')),
            ('24h', _('Last 24 Hours')),
            ('7d', _('Last 7 Days')),
            ('30d', _('Last 30 Days')),
        ]
    
    def queryset(self, request, queryset):
        from datetime import timedelta
        now = timezone.now()
        
        if self.value() == '1h':
            return queryset.filter(last_occurrence__gte=now - timedelta(hours=1))
        elif self.value() == '24h':
            return queryset.filter(last_occurrence__gte=now - timedelta(days=1))
        elif self.value() == '7d':
            return queryset.filter(last_occurrence__gte=now - timedelta(days=7))
        elif self.value() == '30d':
            return queryset.filter(last_occurrence__gte=now - timedelta(days=30))
        
        return queryset


@admin.register(ErrorLog, site=superapp_admin_site)
class ErrorLogAdmin(SuperAppModelAdmin):
    list_display = [
        'error_level_badge',
        'exception_type',
        'short_message',
        'location_link',
        'user_link',
        'count',
        'last_occurrence',
        'resolved_badge'
    ]
    
    list_filter = [
        ErrorLevelDropdownFilter,
        ResolvedStatusDropdownFilter,
        ExceptionTypeDropdownFilter,
        UserDropdownFilter,
        RecentErrorsFilter,
        ('last_occurrence', RangeDateFilter),
        ('first_occurrence', RangeDateFilter),
    ]
    
    search_fields = [
        'exception_type',
        'exception_message',
        'file_path',
        'function_name',
        'user__username',
        'user__email',
        'request_path',
    ]
    
    readonly_fields = [
        'first_occurrence',
        'last_occurrence',
        'created_at',
        'updated_at',
        'debug_details_display',
        'stack_trace_display',
        'count'
    ]
    
    fieldsets = (
        (_('Error Information'), {
            'fields': (
                'error_level',
                'exception_type',
                'exception_message',
                'count',
                'resolved',
                'resolved_by',
                'resolved_at',
                'notes',
            )
        }),
        (_('Location'), {
            'fields': (
                'file_path',
                'line_number',
                'function_name',
            )
        }),
        (_('Request Information'), {
            'fields': (
                'user',
                'request_method',
                'request_path',
                'ip_address',
                'user_agent',
            ),
            'classes': ('collapse',)
        }),
        (_('Debug Information'), {
            'fields': (
                'stack_trace_display',
                'debug_details_display',
            ),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': (
                'first_occurrence',
                'last_occurrence',
                'created_at',
                'updated_at',
            ),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 25
    ordering = ['-last_occurrence']
    
    autocomplete_fields = ['user', 'resolved_by']
    
    actions = ['mark_as_resolved', 'mark_as_unresolved', 'bulk_delete_resolved']
    
    @display(description=_('Level'), ordering='error_level')
    def error_level_badge(self, obj):
        colors = {
            'debug': 'secondary',
            'info': 'info',
            'warning': 'warning',
            'error': 'danger',
            'critical': 'dark'
        }
        color = colors.get(obj.error_level, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_error_level_display().upper()
        )
    
    @display(description=_('Message'), ordering='exception_message')
    def short_message(self, obj):
        message = obj.exception_message[:80]
        if len(obj.exception_message) > 80:
            message += '...'
        return format_html('<span title="{}">{}</span>', obj.exception_message, message)
    
    @display(description=_('Location'))
    def location_link(self, obj):
        if obj.line_number:
            location = f'{obj.file_path.split("/")[-1]}:{obj.line_number}'
            if obj.function_name:
                location += f' ({obj.function_name})'
        else:
            location = obj.file_path.split("/")[-1] if obj.file_path else 'Unknown'
        
        return format_html(
            '<code title="{}">{}</code>',
            obj.file_path,
            location
        )
    
    @display(description=_('User'), ordering='user__username')
    def user_link(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    
    @display(description=_('Status'), ordering='resolved', boolean=True)
    def resolved_badge(self, obj):
        if obj.resolved:
            return format_html(
                '<span class="badge badge-success" title="Resolved by {} on {}">✓ Resolved</span>',
                obj.resolved_by.username if obj.resolved_by else 'Unknown',
                obj.resolved_at.strftime('%Y-%m-%d %H:%M') if obj.resolved_at else 'Unknown'
            )
        return format_html('<span class="badge badge-danger">✗ Open</span>')
    
    @display(description=_('Stack Trace'))
    def stack_trace_display(self, obj):
        if obj.stack_trace:
            return format_html('<pre style="white-space: pre-wrap; max-height: 400px; overflow-y: auto;">{}</pre>', obj.stack_trace)
        return '-'
    
    @display(description=_('Debug Details'))
    def debug_details_display(self, obj):
        if obj.debug_details:
            try:
                formatted_json = json.dumps(obj.debug_details, indent=2, default=str)
                return format_html('<pre style="white-space: pre-wrap; max-height: 400px; overflow-y: auto;">{}</pre>', formatted_json)
            except (TypeError, ValueError):
                return str(obj.debug_details)
        return '-'
    
    @action(
        description=_('Mark selected errors as resolved'),
        attrs={'icon': 'check_circle', 'variant': 'success'}
    )
    def mark_as_resolved(self, request, queryset):
        updated = queryset.filter(resolved=False).update(
            resolved=True,
            resolved_by=request.user,
            resolved_at=timezone.now()
        )
        self.message_user(request, _(f'{updated} error(s) marked as resolved.'))
    
    @action(
        description=_('Mark selected errors as unresolved'),
        attrs={'icon': 'cancel', 'variant': 'warning'}
    )
    def mark_as_unresolved(self, request, queryset):
        updated = queryset.filter(resolved=True).update(
            resolved=False,
            resolved_by=None,
            resolved_at=None
        )
        self.message_user(request, _(f'{updated} error(s) marked as unresolved.'))
    
    @action(
        description=_('Delete resolved errors'),
        attrs={'icon': 'delete', 'variant': 'danger'}
    )
    def bulk_delete_resolved(self, request, queryset):
        deleted_count, _ = queryset.filter(resolved=True).delete()
        self.message_user(request, _(f'{deleted_count} resolved error(s) deleted.'))
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'resolved_by')
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def save_model(self, request, obj, form, change):
        if change and 'resolved' in form.changed_data:
            if obj.resolved and not obj.resolved_by:
                obj.resolved_by = request.user
                obj.resolved_at = timezone.now()
            elif not obj.resolved:
                obj.resolved_by = None
                obj.resolved_at = None
        
        super().save_model(request, obj, form, change)