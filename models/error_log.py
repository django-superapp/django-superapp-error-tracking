import json
import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class ErrorLevel(models.TextChoices):
    DEBUG = 'debug', _('Debug')
    INFO = 'info', _('Info')
    WARNING = 'warning', _('Warning')
    ERROR = 'error', _('Error')
    CRITICAL = 'critical', _('Critical')


class ErrorLog(models.Model):
    error_level = models.CharField(
        max_length=10,
        choices=ErrorLevel.choices,
        default=ErrorLevel.ERROR,
        verbose_name=_('Error Level'),
        db_index=True
    )
    
    exception_type = models.CharField(
        max_length=255,
        verbose_name=_('Exception Type'),
        db_index=True,
        help_text=_('Type of exception (e.g., ValueError, KeyError)')
    )
    
    exception_message = models.TextField(
        verbose_name=_('Exception Message'),
        help_text=_('The error message or exception description')
    )
    
    file_path = models.CharField(
        max_length=500,
        verbose_name=_('File Path'),
        db_index=True,
        help_text=_('Full path to the file where the error occurred')
    )
    
    line_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_('Line Number'),
        help_text=_('Line number where the error occurred')
    )
    
    function_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Function Name'),
        db_index=True,
        help_text=_('Function or method where the error occurred')
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('User'),
        db_index=True,
        help_text=_('User associated with the error (if available)')
    )
    
    request_method = models.CharField(
        max_length=10,
        blank=True,
        verbose_name=_('Request Method'),
        help_text=_('HTTP method (GET, POST, etc.)')
    )
    
    request_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_('Request Path'),
        db_index=True,
        help_text=_('URL path of the request')
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent'),
        help_text=_('Browser user agent string')
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address'),
        db_index=True,
        help_text=_('Client IP address')
    )
    
    stack_trace = models.TextField(
        blank=True,
        verbose_name=_('Stack Trace'),
        help_text=_('Full stack trace of the error')
    )
    
    debug_details = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Debug Details'),
        help_text=_('Additional debug information, request data, context variables, etc.')
    )
    
    resolved = models.BooleanField(
        default=False,
        verbose_name=_('Resolved'),
        db_index=True,
        help_text=_('Whether this error has been resolved')
    )
    
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_errors',
        verbose_name=_('Resolved By'),
        help_text=_('User who marked this error as resolved')
    )
    
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Resolved At'),
        help_text=_('When this error was marked as resolved')
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name=_('Notes'),
        help_text=_('Additional notes about the error or resolution')
    )
    
    count = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Occurrence Count'),
        help_text=_('Number of times this identical error occurred')
    )
    
    first_occurrence = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('First Occurrence'),
        db_index=True,
        help_text=_('When this error first occurred')
    )
    
    last_occurrence = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Last Occurrence'),
        db_index=True,
        help_text=_('When this error last occurred')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Error Log')
        verbose_name_plural = _('Error Logs')
        ordering = ['-last_occurrence']
        indexes = [
            models.Index(fields=['error_level', 'resolved', 'last_occurrence']),
            models.Index(fields=['exception_type', 'file_path']),
            models.Index(fields=['user', 'last_occurrence']),
        ]

    def __str__(self):
        return f'{self.exception_type}: {self.exception_message[:100]}...'

    def save(self, *args, **kwargs):
        if self.debug_details and isinstance(self.debug_details, str):
            try:
                self.debug_details = json.loads(self.debug_details)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f'Invalid JSON in debug_details for ErrorLog {self.id}')
                self.debug_details = {'raw_data': self.debug_details}
        super().save(*args, **kwargs)

    @property
    def location_display(self):
        if self.line_number:
            return f'{self.file_path}:{self.line_number}'
        return self.file_path

    @property
    def is_recent(self):
        from django.utils import timezone
        from datetime import timedelta
        return self.last_occurrence > timezone.now() - timedelta(days=1)
