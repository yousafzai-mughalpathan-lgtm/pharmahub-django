"""
PHARMAHUB - Custom Middleware (FIXED VERSION)
Security, Logging, and Access Control
"""

from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import LoginLog, AdminActivityLog
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class RoleBasedAccessMiddleware(MiddlewareMixin):
    """
    Middleware to enforce role-based access control
    FIXED: Removed failed_login_attempts check
    """
    
    def process_request(self, request):
        # Skip for login, logout, static, media, api endpoints
        exempt_paths = [
            '/admin/login',
            '/api/auth/',
            '/static/',
            '/media/',
            '/api-auth/',
        ]
        
        # Check if path should be exempted
        for path in exempt_paths:
            if request.path.startswith(path):
                return None
        
        # Check if user is authenticated for admin panel
        if request.path.startswith('/admin/'):
            if not request.user.is_authenticated:
                return redirect('/admin/login/')
            
            # Check if user has admin privileges
            if not (request.user.is_staff or request.user.is_superuser):
                # Check if user has is_admin_user attribute
                if hasattr(request.user, 'is_admin_user'):
                    if not request.user.is_admin_user:
                        logger.warning(
                            f"Unauthorized access attempt by {request.user.username} "
                            f"to {request.path}"
                        )
                        return redirect('/')  # Or create an access denied page
                else:
                    # If no is_admin_user attribute, fall back to staff check
                    if not request.user.is_staff:
                        return redirect('/')
        
        return None


class SecurityLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log security-related activities
    FIXED: Removed reference to non-existent failed_login_attempts field
    """
    
    def process_request(self, request):
        # Log suspicious activities
        if request.user.is_authenticated:
            # Check for unusual patterns
            # Instead of checking failed_login_attempts, check LoginLog
            recent_failed = LoginLog.objects.filter(
                user=request.user,
                status='FAILED'
            ).order_by('-created_at')[:5]
            
            if recent_failed.count() >= 5:
                logger.warning(
                    f"User {request.user.username} has {recent_failed.count()} "
                    f"recent failed login attempts"
                )
        
        return None
    
    def process_response(self, request, response):
        # Log 403/404 responses
        if response.status_code in [403, 404] and request.user.is_authenticated:
            logger.info(
                f"User {request.user.username} received {response.status_code} "
                f"for {request.path}"
            )
        
        return response


class ActivityTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track admin activities automatically
    """
    
    TRACKED_ACTIONS = {
        'POST': 'created',
        'PUT': 'updated',
        'PATCH': 'updated',
        'DELETE': 'deleted',
    }
    
    def process_response(self, request, response):
        # Only track authenticated users
        if not request.user.is_authenticated:
            return response
        
        # Check if user is admin (multiple checks for compatibility)
        is_admin = (
            request.user.is_staff or 
            request.user.is_superuser or
            (hasattr(request.user, 'is_admin_user') and request.user.is_admin_user)
        )
        
        if not is_admin:
            return response
        
        # Only track successful modifications
        if response.status_code not in [200, 201, 204]:
            return response
        
        # Skip HTML responses (browsable API)
        content_type = response.get('Content-Type', '')
        if 'text/html' in content_type:
            return response
        
        # Track modifications on API endpoints
        if request.path.startswith('/api/') and request.method in self.TRACKED_ACTIONS:
            try:
                # Extract target from path
                path_parts = request.path.split('/')
                if len(path_parts) >= 3:
                    target_type = path_parts[2]  # e.g., 'pharmacies', 'customers'
                    
                    # Get target ID if available
                    target_id = 0
                    if len(path_parts) >= 4 and path_parts[3].isdigit():
                        target_id = int(path_parts[3])
                    
                    AdminActivityLog.objects.create(
                        admin=request.user,
                        action=f"{target_type}_{self.TRACKED_ACTIONS[request.method]}",
                        target_model=target_type,
                        target_id=target_id,
                        description=f"{request.method} {request.path}",
                        ip_address=self.get_client_ip(request)
                    )
            except Exception as e:
                logger.error(f"Error tracking activity: {str(e)}")
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class RequestValidationMiddleware(MiddlewareMixin):
    """
    Middleware to validate incoming requests
    """
    
    def process_request(self, request):
        # Check for suspicious user agents
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Only log, don't block (for now)
        suspicious_patterns = [
            'sqlmap', 'nikto', 'nmap', 'masscan'
        ]
        
        if any(pattern in user_agent.lower() for pattern in suspicious_patterns):
            logger.warning(
                f"Suspicious user agent detected: {user_agent} "
                f"from IP: {self.get_client_ip(request)}"
            )
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class CORSMiddleware(MiddlewareMixin):
    """
    Handle CORS for API requests
    Note: Better to use django-cors-headers package in production
    """
    
    def process_response(self, request, response):
        if request.path.startswith('/api/'):
            response['Access-Control-Allow-Origin'] = '*'  # Change to your frontend domain
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response['Access-Control-Max-Age'] = '86400'
        
        return response
