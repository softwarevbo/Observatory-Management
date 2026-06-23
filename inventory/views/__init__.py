from .dashboard_views import *
from .adjustment_views import *
from .serial_views import *
from .limit_views import *
from .alert_views import *
from .notification_views import *
from .rental_views import *
from .shortage_views import *
from .superadmin_views import *
from .settings_views import *
from .user_management_views import *
from .chat_views import (
    inv_chat_users,
    inv_chat_messages,
    inv_chat_send,
    inv_chat_poll,
)

"""
Package initializer for inventory view controllers.
Imports all controllers from subfiles for routing mapping.
"""
