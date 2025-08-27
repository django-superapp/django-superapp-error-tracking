# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django SuperApp Error Tracking application that provides comprehensive error logging and monitoring for Django applications. The app tracks application errors, exceptions, and debug information with an optimized admin interface for error management and resolution tracking.

## Key Principles
- Prioritize readability, maintainability, and Django best practices (PEP 8 compliance)
- Modular structure: organize code using Django apps within SuperApp for clear separation and reuse
- Leverage built-in Django features; avoid raw SQL, prefer Django ORM
- Follow strict MVT (Model-View-Template) separation

## Django SuperApp Architecture

### Framework Overview
- Uses a modular architecture where apps extend main SuperApp functionality
- Each app includes independent `settings.py` and `urls.py` automatically integrated by the SuperApp system
- Quickly bootstrap projects using pre-built standalone apps
- Settings are extended via `extend_superapp_settings()` in `settings.py`
- URLs are extended via `extend_superapp_urlpatterns()` and `extend_superapp_admin_urlpatterns()` in `urls.py`

### File Organization Structure
```
superapp/apps/<app_name>/
├── admin/<model_name_slug>.py      # Admin configurations
├── models/<model_name_slug>.py     # Django models
├── views/<view_name>.py            # View functions/classes
├── services/<service_name>.py      # Business logic services
├── signals/<model_name_slug>.py    # Django signals
├── tasks/<task_name>.py            # Celery tasks
├── requirements.txt                # App-specific dependencies
├── settings.py                     # App settings extension
├── urls.py                         # URL patterns extension
└── apps.py                         # Django app configuration
```

Each folder should have an `__init__.py` file to make them packages or to export `__all__` - keep it updated.

## Development Commands

### Backend Commands
- Use `docker-compose exec -ti web python manage.py <command>` to execute Django commands
- Don't launch Python servers on port 8080 (reserved) - use another port or `make web-logs`
- Use `.env.local.example` and `.env.example` for environment variables

## Settings Integration

### App Settings Pattern
`superapp/apps/<app_name>/settings.py`
```python
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy

def extend_superapp_settings(main_settings):
    main_settings['INSTALLED_APPS'] += ['superapp.apps.error_tracking']
    
    # Add admin navigation
    main_settings['UNFOLD']['SIDEBAR']['navigation'] = [
        {
            "title": _("Error Tracking"),
            "icon": "bug_report",
            "items": [
                {
                    "title": _("Error Logs"),
                    "icon": "error",
                    "link": reverse_lazy("admin:error_tracking_errorlog_changelist"),
                    "permission": lambda request: request.user.has_perm("error_tracking.view_errorlog"),
                },
            ]
        },
    ]
```

### URL Integration Pattern
Error tracking app doesn't require custom URL patterns as it uses admin-only interface.

## Admin Integration with django-unfold

### Critical Requirements
**IMPORTANT**: When using Django SuperApp with Unfold admin, you MUST:
- Use `from unfold.decorators import action` instead of `@admin.action` for admin actions
- Use `from unfold.decorators import display` instead of `@admin.display` for display methods
- The `attrs` parameter is crucial for action buttons styling and functionality
- Unfold expects additional attributes (`attrs`, `icon`, `variant`) that Django's decorators don't provide

### Admin File Structure
`superapp/apps/<app_name>/admin/<model_name_slug>.py`
```python
from unfold.decorators import action, display
from superapp.apps.admin_portal.admin import SuperAppModelAdmin
from superapp.apps.admin_portal.sites import superapp_admin_site
from django.contrib import admin

@admin.register(ErrorLog, site=superapp_admin_site)
class ErrorLogAdmin(SuperAppModelAdmin):
    list_display = ['error_level_badge', 'exception_type', 'short_message', 'location_link', 'user_link', 'count', 'last_occurrence', 'resolved_badge']
    search_fields = ['exception_type', 'exception_message', 'file_path', 'function_name', 'user__username']
    autocomplete_fields = ['user', 'resolved_by']  # Prefer for FK/M2M fields
    list_filter = ('error_level', 'resolved', 'last_occurrence')
    list_per_page = 25
    ordering = ('-last_occurrence',)
```

### Admin Best Practices
- Register using `superapp_admin_site` from `superapp.apps.admin_portal.sites`
- Use `SuperAppModelAdmin` based on `unfold.admin.ModelAdmin`
- Prefer `autocomplete_fields` for `ForeignKey` and `ManyToManyField`
- First column in `list_display` should NOT be a foreign key - use a field that opens the model detail

## Django Development Guidelines

### Views and Logic
- Use CBVs (Class-Based Views) for complex logic, FBVs (Function-Based Views) for simple tasks
- Keep business logic in models/forms; views should handle requests/responses only
- Utilize built-in authentication and forms/models validation
- Implement middleware strategically for authentication, logging, caching

### Models and Database
- All models should include `created_at` and `updated_at` timestamp fields
- Use Django ORM; avoid raw SQL
- Optimize queries with `select_related` and `prefetch_related`
- Do NOT update migrations in the `migrations` folder unless there are exceptions or issues

### Services Pattern
- Business logic should live in `superapp/apps/<app_name>/services/<service_name>.py`
- Try to have just two operations: upsert and delete in services
- Keep services focused and reusable

### Error Handling and Signals
- Use built-in error handling mechanisms; customize error pages
- Leverage signals for decoupled logging/error handling
- Signals should live in `superapp/apps/<app_name>/signals/<model_name_slug>.py`

## Frontend Development
- Implement components with dark mode support
- All components should be mobile responsive
- Keep files small and reuse code components
- Organize components correctly and group them logically

## Dependencies and Performance
- Django, Django REST Framework (APIs)
- Celery (background tasks), Redis (caching/task queues)
- PostgreSQL/MySQL (production databases)
- django-unfold (admin UI)
- Use caching framework (Redis/Memcached)
- Apply async views/background tasks (Celery)
- Enforce Django security best practices (CSRF, XSS, SQL injection protections)

## Translation and Internationalization
- Every user-facing string must use `_('XXX')` from Django translation
- Import: `from django.utils.translation import gettext_lazy as _`

## Development Setup

Bootstrap this app into an existing Django SuperApp project:

```bash
cd my_superapp
cd superapp/apps
# Copy the error_tracking directory to your SuperApp project
cp -r /path/to/error_tracking ./
cd ../../
```

## Error Tracking Features

### Core Capabilities
- **Comprehensive Error Logging**: Tracks exceptions, custom errors, and debug information
- **Request Context Capture**: Automatically captures user, IP, request method, and path
- **Duplicate Detection**: Groups identical errors and tracks occurrence count
- **Resolution Tracking**: Mark errors as resolved with timestamps and user tracking
- **Advanced Admin Interface**: Optimized filters and displays for high-volume error data
- **Stack Trace Analysis**: Full stack trace capture and formatted display

### Error Model Structure
- **Error Levels**: Debug, Info, Warning, Error, Critical
- **Location Tracking**: File path, line number, function name
- **User Context**: Associated user, IP address, request details
- **Debug Information**: JSON field for additional context and variables
- **Resolution Management**: Resolved status, resolver, resolution notes

### Services
- **ErrorTracker**: Main error tracking service with utility functions
- **Request Context Extraction**: Automatic request details capture
- **Sensitive Data Filtering**: Filters passwords and tokens from logged data

### Usage Examples
```python
# Track exceptions
from superapp.apps.error_tracking.services import track_error, track_exception

try:
    risky_operation()
except Exception as e:
    track_error(exception=e, request=request, custom_context="upload_process")

# Track from except block
try:
    dangerous_code()
except:
    track_exception(request=request, user_action="file_upload")

# Track custom errors
track_error(
    custom_message="User attempted invalid operation",
    error_level="warning",
    request=request,
    operation_id=123
)
```

### Environment Configuration
Set `DEBUG_ERROR_TRACKING=true` to enable detailed error tracking logs.
