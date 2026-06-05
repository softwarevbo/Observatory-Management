"""
This package contains views for the accounts application.
To keep the codebase modular, views are split into three logical modules:
1. auth_views.py: Handles login, logout, and password change logic for users.
2. user_management_views.py: Handles admin tasks (CRUD operations for PM, inventory, and telescope users).
3. profile_views.py: Handles self-service user profile dashboards and settings interfaces.

By importing everything (*) in this __init__.py, we make these views importable directly 
from accounts.views (e.g. from accounts import views).
"""

from .auth_views import *
from .user_management_views import *
from .profile_views import *
