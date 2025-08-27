import os
import sys
import traceback
import inspect
import logging
from typing import Optional, Dict, Any, Union
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from superapp.apps.error_tracking.models import ErrorLog, ErrorLevel

User = get_user_model()
logger = logging.getLogger(__name__)

# Check for debug logging from environment
DEBUG_ERROR_TRACKING = os.environ.get('DEBUG_ERROR_TRACKING', 'false').lower() == 'true'

def get_client_ip(request):
    """Extract client IP address from request."""
    if not request:
        return None
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        return x_real_ip.strip()
        
    return request.META.get('REMOTE_ADDR')


def get_request_details(request) -> Dict[str, Any]:
    """Extract useful details from Django request object."""
    if not request:
        return {}
    
    details = {
        'method': getattr(request, 'method', ''),
        'path': getattr(request, 'path', ''),
        'full_path': getattr(request, 'get_full_path', lambda: '')(),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'ip_address': get_client_ip(request),
        'session_key': getattr(request, 'session', {}).get('session_key', ''),
        'is_ajax': getattr(request, 'headers', {}).get('X-Requested-With') == 'XMLHttpRequest',
        'is_secure': getattr(request, 'is_secure', lambda: False)(),
    }
    
    # Add GET/POST data (be careful with sensitive data)
    if hasattr(request, 'GET') and request.GET:
        details['get_params'] = dict(request.GET.items())
    
    if hasattr(request, 'POST') and request.POST:
        # Filter out sensitive fields
        sensitive_fields = {'password', 'token', 'api_key', 'secret', 'csrf_token'}
        post_data = {}
        for key, value in request.POST.items():
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                post_data[key] = '[FILTERED]'
            else:
                post_data[key] = value
        details['post_params'] = post_data
    
    return details


def extract_traceback_info(exception: Exception) -> Dict[str, Any]:
    """Extract detailed information from exception traceback."""
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    if not exc_traceback:
        # If no current exception, try to get traceback from the exception
        exc_traceback = exception.__traceback__
    
    info = {
        'exception_type': exception.__class__.__name__,
        'exception_message': str(exception),
        'stack_trace': '',
        'file_path': '',
        'line_number': None,
        'function_name': '',
    }
    
    if exc_traceback:
        # Get full stack trace
        info['stack_trace'] = ''.join(traceback.format_exception(
            exc_type or type(exception), 
            exc_value or exception, 
            exc_traceback
        ))
        
        # Get the last frame (where the error occurred)
        last_frame = exc_traceback
        while last_frame.tb_next:
            last_frame = last_frame.tb_next
        
        frame = last_frame.tb_frame
        info['file_path'] = frame.f_code.co_filename
        info['line_number'] = last_frame.tb_lineno
        info['function_name'] = frame.f_code.co_name
    
    return info


def track_error(
    exception: Optional[Union[Exception, str]] = None,
    error_level: str = ErrorLevel.ERROR,
    custom_message: Optional[str] = None,
    debug_details: Optional[Dict[str, Any]] = None,
    request=None,
    user: Optional[User] = None,
    file_path: Optional[str] = None,
    line_number: Optional[int] = None,
    function_name: Optional[str] = None,
    **kwargs
) -> Optional[ErrorLog]:
    """
    Track application errors and save them to ErrorLog model.
    
    Args:
        exception: Exception object or error message string
        error_level: Error level (debug, info, warning, error, critical)
        custom_message: Custom error message (overrides exception message)
        debug_details: Additional debug information dictionary
        request: Django request object (for extracting request details)
        user: User object (if not in request)
        file_path: Override file path detection
        line_number: Override line number detection
        function_name: Override function name detection
        **kwargs: Additional fields to add to debug_details
    
    Returns:
        ErrorLog instance or None if tracking failed
    """
    try:
        if DEBUG_ERROR_TRACKING:
            logger.debug(f"[ERROR_TRACKING] Starting error tracking for: {exception}")
        
        # Initialize error info
        error_info = {
            'exception_type': 'CustomError',
            'exception_message': custom_message or str(exception) if exception else 'Unknown error',
            'stack_trace': '',
            'file_path': file_path or '',
            'line_number': line_number,
            'function_name': function_name or '',
        }
        
        # Extract traceback info if exception is provided
        if isinstance(exception, Exception):
            error_info.update(extract_traceback_info(exception))
            
        # If no explicit file/line info and we have caller info, use it
        if not error_info['file_path'] and not file_path:
            caller_frame = inspect.currentframe().f_back
            if caller_frame:
                error_info['file_path'] = caller_frame.f_code.co_filename
                error_info['line_number'] = caller_frame.f_lineno
                error_info['function_name'] = caller_frame.f_code.co_name
        
        # Get user from request if not provided
        if not user and request and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
        
        # Prepare debug details
        combined_debug_details = debug_details or {}
        combined_debug_details.update(kwargs)
        
        # Add request details if available
        if request:
            request_details = get_request_details(request)
            combined_debug_details['request'] = request_details
            
        # Add user details if available
        if user:
            combined_debug_details['user'] = {
                'id': user.id,
                'username': getattr(user, 'username', ''),
                'email': getattr(user, 'email', ''),
                'is_staff': getattr(user, 'is_staff', False),
                'is_superuser': getattr(user, 'is_superuser', False),
            }
        
        # Add environment information
        combined_debug_details['environment'] = {
            'django_version': getattr(settings, 'DJANGO_VERSION', 'unknown'),
            'debug': getattr(settings, 'DEBUG', False),
            'python_version': sys.version,
            'platform': sys.platform,
        }
        
        if DEBUG_ERROR_TRACKING:
            logger.debug(f"[ERROR_TRACKING] Prepared error info: {error_info}")
            logger.debug(f"[ERROR_TRACKING] Debug details keys: {list(combined_debug_details.keys())}")
        
        # Try to find existing error to update count
        existing_error = ErrorLog.objects.filter(
            exception_type=error_info['exception_type'],
            exception_message=error_info['exception_message'],
            file_path=error_info['file_path'],
            line_number=error_info['line_number'],
            resolved=False
        ).first()
        
        if existing_error:
            existing_error.count += 1
            existing_error.last_occurrence = timezone.now()
            existing_error.debug_details.update(combined_debug_details)
            existing_error.save()
            
            if DEBUG_ERROR_TRACKING:
                logger.debug(f"[ERROR_TRACKING] Updated existing error #{existing_error.id}, count: {existing_error.count}")
            
            return existing_error
        
        # Create new error log
        error_log = ErrorLog.objects.create(
            error_level=error_level,
            exception_type=error_info['exception_type'],
            exception_message=error_info['exception_message'],
            file_path=error_info['file_path'],
            line_number=error_info['line_number'],
            function_name=error_info['function_name'],
            user=user,
            request_method=getattr(request, 'method', '') if request else '',
            request_path=getattr(request, 'path', '') if request else '',
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
            ip_address=get_client_ip(request),
            stack_trace=error_info['stack_trace'],
            debug_details=combined_debug_details,
        )
        
        if DEBUG_ERROR_TRACKING:
            logger.debug(f"[ERROR_TRACKING] Created new error log #{error_log.id}")
        
        # Log to Django logger as well
        log_message = f"Error tracked #{error_log.id}: {error_info['exception_type']} - {error_info['exception_message']}"
        if error_level == ErrorLevel.CRITICAL:
            logger.critical(log_message)
        elif error_level == ErrorLevel.ERROR:
            logger.error(log_message)
        elif error_level == ErrorLevel.WARNING:
            logger.warning(log_message)
        elif error_level == ErrorLevel.INFO:
            logger.info(log_message)
        else:
            logger.debug(log_message)
        
        return error_log
        
    except Exception as tracking_error:
        # Don't let error tracking itself fail the application
        logger.error(f"Error tracking failed: {tracking_error}", exc_info=True)
        return None


def track_exception(request=None, **kwargs):
    """
    Convenience function to track the current exception.
    Should be called from within an except block.
    """
    exc_type, exc_value, exc_traceback = sys.exc_info()
    if exc_value:
        return track_error(exception=exc_value, request=request, **kwargs)
    return None


def track_warning(message: str, request=None, **kwargs):
    """Convenience function to track warnings."""
    return track_error(
        exception=message,
        error_level=ErrorLevel.WARNING,
        request=request,
        **kwargs
    )


def track_info(message: str, request=None, **kwargs):
    """Convenience function to track info messages."""
    return track_error(
        exception=message,
        error_level=ErrorLevel.INFO,
        request=request,
        **kwargs
    )


def track_critical(exception: Union[Exception, str], request=None, **kwargs):
    """Convenience function to track critical errors."""
    return track_error(
        exception=exception,
        error_level=ErrorLevel.CRITICAL,
        request=request,
        **kwargs
    )