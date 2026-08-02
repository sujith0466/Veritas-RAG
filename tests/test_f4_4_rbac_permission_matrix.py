"""Tests for F4.4: RBAC Permission Enforcement (Full Matrix)."""


from backend.core.permissions.guards import evaluate_permission_access, evaluate_role_access
from backend.core.permissions.rbac import Role
from backend.core.permissions.registry import Permission, get_permission_registry


def test_permission_registry_singleton():
    reg1 = get_permission_registry()
    reg2 = get_permission_registry()
    assert reg1 is reg2


def test_owner_has_all_workspace_permissions():
    registry = get_permission_registry()

    assert registry.has_permission(Role.OWNER, Permission.WORKSPACE_DELETE) is True
    assert registry.has_permission(Role.OWNER, Permission.WORKSPACE_ARCHIVE) is True
    assert registry.has_permission(Role.OWNER, Permission.BILLING_UPDATE) is True
    assert registry.has_permission(Role.OWNER, Permission.USERS_MEMBER_UPDATE_ROLE) is True
    assert registry.has_permission(Role.OWNER, Permission.INVITATIONS_SEND) is True
    assert registry.has_permission(Role.OWNER, Permission.DOCUMENTS_CREATE) is True


def test_admin_cannot_delete_workspace_or_manage_billing_update():
    registry = get_permission_registry()

    assert registry.has_permission(Role.ADMIN, Permission.WORKSPACE_DELETE) is False
    assert registry.has_permission(Role.ADMIN, Permission.BILLING_UPDATE) is False
    # Admin can manage users and invitations
    assert registry.has_permission(Role.ADMIN, Permission.USERS_MEMBER_LIST) is True
    assert registry.has_permission(Role.ADMIN, Permission.INVITATIONS_SEND) is True
    assert registry.has_permission(Role.ADMIN, Permission.DOCUMENTS_CREATE) is True


def test_member_and_viewer_boundaries():
    registry = get_permission_registry()

    # Member can create documents and run queries
    assert registry.has_permission(Role.MEMBER, Permission.DOCUMENTS_CREATE) is True
    assert registry.has_permission(Role.MEMBER, Permission.RAG_QUERY_EXECUTE) is True
    assert registry.has_permission(Role.MEMBER, Permission.INVITATIONS_SEND) is False
    assert registry.has_permission(Role.MEMBER, Permission.USERS_MEMBER_UPDATE_ROLE) is False

    # Viewer has read-only access
    assert registry.has_permission(Role.VIEWER, Permission.DOCUMENTS_READ) is True
    assert registry.has_permission(Role.VIEWER, Permission.RAG_QUERY_EXECUTE) is True
    assert registry.has_permission(Role.VIEWER, Permission.DOCUMENTS_CREATE) is False
    assert registry.has_permission(Role.VIEWER, Permission.DOCUMENTS_DELETE) is False


def test_platform_admin_full_override():
    registry = get_permission_registry()

    for perm in Permission:
        assert registry.has_permission(Role.PLATFORM_ADMIN, perm) is True


def test_suspended_user_explicit_deny():
    registry = get_permission_registry()

    # Even owner gets denied if suspended
    assert registry.has_permission(Role.OWNER, Permission.WORKSPACE_READ, is_suspended=True) is False
    assert registry.has_permission(Role.ADMIN, Permission.DOCUMENTS_READ, is_suspended=True) is False
    assert registry.has_permission(Role.MEMBER, Permission.RAG_QUERY_EXECUTE, is_suspended=True) is False


def test_evaluate_guards():
    assert evaluate_role_access(Role.OWNER, (Role.ADMIN, Role.MEMBER)) is True
    assert evaluate_role_access(Role.MEMBER, (Role.VIEWER,)) is False
    assert evaluate_role_access(Role.VIEWER, (Role.VIEWER,)) is True
    assert evaluate_role_access(Role.VIEWER, (Role.VIEWER,), is_suspended=True) is False

    assert evaluate_permission_access(Role.ADMIN, Permission.INVITATIONS_SEND) is True
    assert evaluate_permission_access(Role.VIEWER, Permission.INVITATIONS_SEND) is False
