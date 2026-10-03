"""
Role-Based Access Control (RBAC) Centralized Authorization System.

This module provides the single source of truth for user roles, permission definitions,
canonical role normalization, login entry point validation, module level authorization,
and user management permission rules.
"""

from typing import Any, Optional, Set

# ─── 1. Canonical Role Definitions ───────────────────────────────────────────

ROLE_ROOT = "ROOT"
ROLE_PM_ADMIN = "PM_ADMIN"
ROLE_PM_MEMBER = "PM_MEMBER"
ROLE_TCS_ADMIN = "TCS_ADMIN"
ROLE_TCS_MEMBER = "TCS_MEMBER"
ROLE_TM_ADMIN = "TCS_ADMIN"
ROLE_TM_MEMBER = "TCS_MEMBER"
ROLE_IM_ADMIN = "IM_ADMIN"
ROLE_IM_MEMBER = "IM_MEMBER"

ALL_ROLES = [
    (ROLE_ROOT, "Root Administrator"),
    (ROLE_PM_ADMIN, "PM Admin"),
    (ROLE_PM_MEMBER, "PM Member"),
    (ROLE_TCS_ADMIN, "TCS Admin"),
    (ROLE_TCS_MEMBER, "TCS Member"),
    (ROLE_IM_ADMIN, "IM Admin"),
    (ROLE_IM_MEMBER, "IM Member"),
]

ROLE_VALUES = {r[0] for r in ALL_ROLES} | {"TM_ADMIN", "TM_MEMBER"}

# ─── 2. Permission Definitions & Matrix ──────────────────────────────────────

# Module Access Permissions
PERMISSION_PROJECT_ACCESS = "PROJECT_ACCESS"
PERMISSION_TELESCOPE_ACCESS = "TELESCOPE_ACCESS"
PERMISSION_INVENTORY_ACCESS = "INVENTORY_ACCESS"

# User Management Permissions
PERMISSION_PROJECT_USER_MANAGE = "PROJECT_USER_MANAGE"
PERMISSION_TELESCOPE_USER_MANAGE = "TELESCOPE_USER_MANAGE"
PERMISSION_INVENTORY_USER_MANAGE = "INVENTORY_USER_MANAGE"

# Highest Level Admin Management
PERMISSION_ADMIN_MANAGE = "ADMIN_MANAGE"

PERMISSION_MATRIX = {
    PERMISSION_PROJECT_ACCESS: {ROLE_ROOT, ROLE_PM_ADMIN, ROLE_PM_MEMBER},
    PERMISSION_TELESCOPE_ACCESS: {ROLE_ROOT, ROLE_TM_ADMIN, ROLE_TM_MEMBER},
    PERMISSION_INVENTORY_ACCESS: {ROLE_ROOT, ROLE_IM_ADMIN, ROLE_IM_MEMBER},
    PERMISSION_PROJECT_USER_MANAGE: {ROLE_ROOT, ROLE_PM_ADMIN},
    PERMISSION_TELESCOPE_USER_MANAGE: {ROLE_ROOT, ROLE_TM_ADMIN},
    PERMISSION_INVENTORY_USER_MANAGE: {ROLE_ROOT, ROLE_IM_ADMIN},
    PERMISSION_ADMIN_MANAGE: {ROLE_ROOT},
}

# Login Entry Point Restrictions
LOGIN_ALLOWED_ROLES = {
    "project": {ROLE_ROOT, ROLE_PM_ADMIN, ROLE_PM_MEMBER},
    "telescope": {ROLE_ROOT, ROLE_TM_ADMIN, ROLE_TM_MEMBER},
    "inventory": {ROLE_ROOT, ROLE_IM_ADMIN, ROLE_IM_MEMBER},
}

# ─── 3. Canonical Role Resolution ───────────────────────────────────────────

def get_canonical_role(user: Any) -> Optional[str]:
    """
    Normalizes a user object (Standard User or InventoryUser) or string role into one of the 7 canonical roles:
    ROLE_ROOT, ROLE_PM_ADMIN, ROLE_PM_MEMBER, ROLE_TM_ADMIN, ROLE_TM_MEMBER, ROLE_IM_ADMIN, ROLE_IM_MEMBER.
    """
    if user is None:
        return None

    # Handle string input directly
    if isinstance(user, str):
        role_str = user.strip()
        if role_str in ["TM_ADMIN", "TCS_ADMIN"]:
            return ROLE_TCS_ADMIN
        if role_str in ["TM_MEMBER", "TCS_MEMBER"]:
            return ROLE_TCS_MEMBER
        if role_str in ROLE_VALUES:
            return role_str
        if role_str.upper() in ["ROOT", "ADMIN", "SUPERADMIN", "SUPER_ADMIN"]:
            return ROLE_ROOT
        if role_str in ["project_manager", "member", "student", "user"]:
            return ROLE_PM_MEMBER
        if role_str in ["branch_admin"]:
            return ROLE_IM_ADMIN
        if role_str in ["staff"]:
            return ROLE_IM_MEMBER
        return ROLE_PM_MEMBER

    # Handle AnonymousUser
    if not getattr(user, "is_authenticated", False):
        return None

    # Handle dedicated model instances explicitly
    if hasattr(user, "_meta"):
        model_name = user._meta.model_name
        if model_name == "telescopeuser":
            role = getattr(user, "role", "") or ""
            if role in ["admin", "TCS_ADMIN", "TM_ADMIN"] or getattr(user, "is_telescope_admin", False):
                return ROLE_TCS_ADMIN
            return ROLE_TCS_MEMBER
        if model_name == "inventoryuser":
            role = getattr(user, "role", "") or ""
            if role in ["super_admin", "ROOT"]:
                return ROLE_ROOT
            if role in ["branch_admin", "IM_ADMIN"]:
                return ROLE_IM_ADMIN
            return ROLE_IM_MEMBER

    # Check superuser flag first -> ROOT
    if getattr(user, "is_superuser", False):
        return ROLE_ROOT

    role = getattr(user, "role", "") or ""
    role = role.strip()

    if role in ["TM_ADMIN", "TCS_ADMIN"]:
        return ROLE_TCS_ADMIN
    if role in ["TM_MEMBER", "TCS_MEMBER"]:
        return ROLE_TCS_MEMBER

    # Direct canonical match
    if role in ROLE_VALUES:
        return role

    # Explicit alias matches
    if role.upper() in ["ROOT", "ADMIN"]:
        # If user model has specific module flags disabling PM but enabling TM/IM:
        if getattr(user, "can_access_telescope", False) and not getattr(user, "can_access_pm", True):
            return ROLE_TM_ADMIN
        if getattr(user, "can_access_inventory", False) and not getattr(user, "can_access_pm", True):
            return ROLE_IM_ADMIN
        return ROLE_ROOT

    if role == "super_admin":
        # InventoryUser super_admin maps to ROOT or IM_ADMIN
        if hasattr(user, "_meta") and user._meta.model_name == "inventoryuser":
            return ROLE_ROOT
        return ROLE_ROOT

    if role == "branch_admin":
        return ROLE_IM_ADMIN

    if role == "staff":
        return ROLE_IM_MEMBER

    if role in ["member", "project_manager", "student", "user", ""]:
        can_tm = getattr(user, "can_access_telescope", False)
        can_im = getattr(user, "can_access_inventory", False)
        is_tele_admin = getattr(user, "is_telescope_admin", False)

        if can_tm:
            return ROLE_TM_ADMIN if is_tele_admin else ROLE_TM_MEMBER
        if can_im:
            return ROLE_IM_MEMBER
        return ROLE_PM_MEMBER

    return ROLE_PM_MEMBER


# ─── 4. Permission Checking Functions ────────────────────────────────────────

def has_permission(user: Any, permission_name: str) -> bool:
    """
    Checks if a user has a specific RBAC permission.
    """
    canonical_role = get_canonical_role(user)
    if not canonical_role:
        return False

    allowed_roles = PERMISSION_MATRIX.get(permission_name)
    if allowed_roles is None:
        return False

    return canonical_role in allowed_roles


def can_login_to_module(user: Any, module_name: str) -> bool:
    """
    Validates whether a user role is permitted to log into a specific management module.
    module_name can be 'project', 'telescope', or 'inventory'.
    """
    canonical_role = get_canonical_role(user)
    if not canonical_role:
        return False

    allowed = LOGIN_ALLOWED_ROLES.get(module_name)
    if not allowed:
        return False

    return canonical_role in allowed


# ─── 5. User Management Authorization Rules ─────────────────────────────────

def can_manage_user_list(admin_user: Any, tab: str) -> bool:
    """
    Determines if an admin user can view/manage the user list tab.
    tab can be 'pm', 'telescope', or 'inventory'.
    """
    canonical_role = get_canonical_role(admin_user)
    if not canonical_role:
        return False

    if canonical_role == ROLE_ROOT:
        return True

    if canonical_role == ROLE_PM_ADMIN and tab == "pm":
        return True

    if canonical_role == ROLE_TM_ADMIN and tab == "telescope":
        return True

    if canonical_role == ROLE_IM_ADMIN and tab == "inventory":
        return True

    return False


def can_manage_target_user(admin_user: Any, target_user: Any) -> bool:
    """
    Enforces role hierarchy and user management permissions:
    - ROOT can manage all users.
    - Non-ROOT admins (PM_ADMIN, TM_ADMIN, IM_ADMIN) CANNOT view/edit credentials or reset password of ROOT superadmins.
    - PM_ADMIN can manage PM_MEMBER only.
    - TM_ADMIN / TCS_ADMIN can manage TM_MEMBER / TCS_MEMBER only.
    - IM_ADMIN can manage IM_MEMBER only.
    - Members cannot manage any users.
    """
    admin_role = get_canonical_role(admin_user)
    target_role = get_canonical_role(target_user)

    if not admin_role or not target_role:
        return False

    is_target_root = (
        target_role == ROLE_ROOT
        or getattr(target_user, "is_superuser", False)
        or getattr(target_user, "role", "") in ["ROOT", "super_admin"]
    )
    is_admin_root = (
        admin_role == ROLE_ROOT
        or getattr(admin_user, "is_superuser", False)
        or getattr(admin_user, "role", "") in ["ROOT", "super_admin"]
    )

    if is_target_root:
        return is_admin_root

    if is_admin_root:
        return True

    if admin_role == ROLE_PM_ADMIN:
        return target_role == ROLE_PM_MEMBER

    if admin_role in [ROLE_TCS_ADMIN, ROLE_TM_ADMIN]:
        return target_role in [ROLE_TCS_MEMBER, ROLE_TM_MEMBER]

    if admin_role == ROLE_IM_ADMIN:
        return target_role == ROLE_IM_MEMBER

    return False


def get_assignable_roles(admin_user: Any) -> list:
    """
    Returns the list of role tuples (role_code, display_label) that admin_user is authorized to assign.
    - ROOT can assign all roles (PM_ADMIN, PM_MEMBER, TM_ADMIN, TM_MEMBER, IM_ADMIN, IM_MEMBER).
    - PM_ADMIN can assign PM_MEMBER only.
    - TM_ADMIN can assign TM_MEMBER only.
    - IM_ADMIN can assign IM_MEMBER only.
    """
    admin_role = get_canonical_role(admin_user)
    if not admin_role:
        return []

    if admin_role == ROLE_ROOT:
        return [
            (ROLE_PM_ADMIN, "PM Admin"),
            (ROLE_PM_MEMBER, "PM Member"),
            (ROLE_TCS_ADMIN, "TCS Admin"),
            (ROLE_TCS_MEMBER, "TCS Member"),
            (ROLE_IM_ADMIN, "IM Admin"),
            (ROLE_IM_MEMBER, "IM Member"),
        ]

    if admin_role == ROLE_PM_ADMIN:
        return [(ROLE_PM_MEMBER, "PM Member")]

    if admin_role == ROLE_TCS_ADMIN:
        return [(ROLE_TCS_MEMBER, "TCS Member")]

    if admin_role == ROLE_IM_ADMIN:
        return [(ROLE_IM_MEMBER, "IM Member")]

    return []


def can_assign_role(admin_user: Any, requested_role: str) -> bool:
    """
    Checks if admin_user can assign requested_role to another user.
    """
    assignable = get_assignable_roles(admin_user)
    allowed_codes = {r[0] for r in assignable}
    canonical_requested = get_canonical_role(requested_role) or requested_role
    return canonical_requested in allowed_codes


def get_default_redirect_for_role(user: Any) -> str:
    """
    Returns the default dashboard URL for a user based on their canonical role.
    """
    canonical_role = get_canonical_role(user)

    if canonical_role in {ROLE_ROOT, ROLE_PM_ADMIN, ROLE_PM_MEMBER}:
        return "/projectmanagement/dashboard/"

    elif canonical_role in {ROLE_TM_ADMIN, ROLE_TM_MEMBER}:
        return "/telescopecontrol/"
    elif canonical_role in {ROLE_IM_ADMIN, ROLE_IM_MEMBER}:
        return "/inventorymanagement/dashboard/"

    return "/projectmanagement/dashboard/"

