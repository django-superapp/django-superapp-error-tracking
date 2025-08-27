from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy


def extend_superapp_settings(main_settings):
    main_settings['INSTALLED_APPS'] += [
        'superapp.apps.error_tracking',
    ]

    # Add error tracking to admin navigation
    if 'UNFOLD' not in main_settings:
        main_settings['UNFOLD'] = {}

    if 'SIDEBAR' not in main_settings['UNFOLD']:
        main_settings['UNFOLD']['SIDEBAR'] = {}

    if 'navigation' not in main_settings['UNFOLD']['SIDEBAR']:
        main_settings['UNFOLD']['SIDEBAR']['navigation'] = []

    # Add Error Tracking navigation section
    error_tracking_nav = {
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
    }

    main_settings['UNFOLD']['SIDEBAR']['navigation'].append(error_tracking_nav)
