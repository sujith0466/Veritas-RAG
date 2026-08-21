"""Veritas RAG — Permissions and RBAC foundation package."""

from .guards import evaluate_permission_access, evaluate_role_access
from .rbac import Role
from .registry import Permission, PermissionRegistry, get_permission_registry

__all__ = [
    "Permission",
    "PermissionRegistry",
    "Role",
    "evaluate_permission_access",
    "evaluate_role_access",
    "get_permission_registry",
]
