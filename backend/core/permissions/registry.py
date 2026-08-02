"""Permission Registry and Hierarchical RBAC Matrix.

Centralizes all permission definitions and role-to-permission mappings across 16+ categories.
Provides O(1) in-memory lookups, inheritance, and explicit deny semantics.
"""

from enum import StrEnum
from functools import lru_cache

from .rbac import Role


class Permission(StrEnum):
    """Granular permissions across all platform and workspace capabilities."""

    # Legacy Capabilities (for backward compatibility)
    READ_KNOWLEDGE = "read:knowledge"
    WRITE_KNOWLEDGE = "write:knowledge"
    RUN_QUERY = "run:query"
    ADMIN_SETTINGS = "admin:settings"
    VIEW_DETAILED_HEALTH = "view:detailed_health"
    MANAGE_USERS = "manage:users"
    MANAGE_KEYS = "manage:keys"

    # Category 1: Workspace
    WORKSPACE_READ = "workspace:workspace:read"
    WORKSPACE_UPDATE = "workspace:workspace:update"
    WORKSPACE_DELETE = "workspace:workspace:delete"
    WORKSPACE_ARCHIVE = "workspace:workspace:archive"
    WORKSPACE_RESTORE = "workspace:workspace:restore"
    WORKSPACE_SUSPEND = "workspace:workspace:suspend"

    # Category 2: Settings & Branding
    SETTINGS_READ = "settings:settings:read"
    SETTINGS_UPDATE = "settings:settings:update"
    SETTINGS_BRANDING_UPDATE = "settings:branding:update"

    # Category 3: Feature Flags
    FEATURE_FLAGS_READ = "feature_flags:flag:read"
    FEATURE_FLAGS_MANAGE = "feature_flags:flag:manage"

    # Category 4: Users / Workspace Members
    USERS_MEMBER_LIST = "users:member:list"
    USERS_MEMBER_READ = "users:member:read"
    USERS_MEMBER_UPDATE_ROLE = "users:member:update_role"
    USERS_MEMBER_SUSPEND = "users:member:suspend"
    USERS_MEMBER_RESTORE = "users:member:restore"
    USERS_MEMBER_REMOVE = "users:member:remove"
    USERS_MEMBER_BULK = "users:member:bulk"

    # Category 5: Invitations
    INVITATIONS_SEND = "invitations:invitation:send"
    INVITATIONS_LIST = "invitations:invitation:list"
    INVITATIONS_RESEND = "invitations:invitation:resend"
    INVITATIONS_REVOKE = "invitations:invitation:revoke"
    INVITATIONS_VERIFY = "invitations:invitation:verify"
    INVITATIONS_ACCEPT = "invitations:invitation:accept"

    # Category 6: Documents
    DOCUMENTS_READ = "documents:file:read"
    DOCUMENTS_CREATE = "documents:file:create"
    DOCUMENTS_UPDATE = "documents:file:update"
    DOCUMENTS_DELETE = "documents:file:delete"

    # Category 7: Chunks
    CHUNKS_READ = "chunks:chunk:read"
    CHUNKS_MANAGE = "chunks:chunk:manage"

    # Category 8: Embeddings
    EMBEDDINGS_READ = "embeddings:embedding:read"
    EMBEDDINGS_GENERATE = "embeddings:embedding:generate"

    # Category 9: Chat
    CHAT_SESSION_CREATE = "chat:session:create"
    CHAT_SESSION_READ = "chat:session:read"
    CHAT_SESSION_DELETE = "chat:session:delete"
    CHAT_MESSAGE_CREATE = "chat:message:create"

    # Category 10: RAG
    RAG_QUERY_EXECUTE = "rag:query:execute"
    RAG_EVALUATION_READ = "rag:evaluation:read"

    # Category 11: API Keys
    APIKEYS_READ = "apikeys:key:read"
    APIKEYS_CREATE = "apikeys:key:create"
    APIKEYS_REVOKE = "apikeys:key:revoke"

    # Category 12: Billing
    BILLING_READ = "billing:subscription:read"
    BILLING_UPDATE = "billing:subscription:update"
    BILLING_INVOICES_READ = "billing:invoices:read"

    # Category 13: Analytics
    ANALYTICS_READ = "analytics:metrics:read"
    ANALYTICS_EXPORT = "analytics:metrics:export"

    # Category 14: Audit Logs
    AUDIT_LOGS_READ = "audit:logs:read"
    AUDIT_LOGS_EXPORT = "audit:logs:export"

    # Category 15: Integrations
    INTEGRATIONS_READ = "integrations:integration:read"
    INTEGRATIONS_CONFIGURE = "integrations:integration:configure"


class PermissionRegistry:
    """Registry centralizing role-to-permission mappings and O(1) lookup logic."""

    def __init__(self) -> None:
        self._role_permissions: dict[Role, set[str]] = {}
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        """Register baseline role-to-permission mappings across hierarchies."""
        all_perms: set[str] = {p.value for p in Permission}

        # Viewer: Read-only access
        viewer_perms: set[str] = {
            Permission.READ_KNOWLEDGE.value,
            Permission.WORKSPACE_READ.value,
            Permission.SETTINGS_READ.value,
            Permission.DOCUMENTS_READ.value,
            Permission.CHUNKS_READ.value,
            Permission.EMBEDDINGS_READ.value,
            Permission.CHAT_SESSION_READ.value,
            Permission.CHAT_SESSION_CREATE.value,
            Permission.CHAT_MESSAGE_CREATE.value,
            Permission.RAG_QUERY_EXECUTE.value,
            Permission.RUN_QUERY.value,
            Permission.ANALYTICS_READ.value,
            Permission.INVITATIONS_VERIFY.value,
            Permission.INVITATIONS_ACCEPT.value,
        }

        # Member: Viewer + Document mutations + API key creation + RAG evaluation
        member_perms: set[str] = set(viewer_perms) | {
            Permission.WRITE_KNOWLEDGE.value,
            Permission.DOCUMENTS_CREATE.value,
            Permission.DOCUMENTS_UPDATE.value,
            Permission.DOCUMENTS_DELETE.value,
            Permission.CHUNKS_MANAGE.value,
            Permission.EMBEDDINGS_GENERATE.value,
            Permission.CHAT_SESSION_DELETE.value,
            Permission.RAG_EVALUATION_READ.value,
            Permission.APIKEYS_READ.value,
            Permission.APIKEYS_CREATE.value,
            Permission.APIKEYS_REVOKE.value,
            Permission.MANAGE_KEYS.value,
        }

        # Engineer / Analyst mappings
        analyst_perms: set[str] = set(viewer_perms) | {
            Permission.RAG_EVALUATION_READ.value,
            Permission.ANALYTICS_EXPORT.value,
            Permission.AUDIT_LOGS_READ.value,
        }
        engineer_perms: set[str] = set(member_perms) | {
            Permission.INTEGRATIONS_READ.value,
            Permission.INTEGRATIONS_CONFIGURE.value,
            Permission.FEATURE_FLAGS_READ.value,
        }

        # Admin: Member + Settings + Member management + Invitations + Audit logs + Integrations
        admin_perms: set[str] = set(member_perms) | {
            Permission.ADMIN_SETTINGS.value,
            Permission.VIEW_DETAILED_HEALTH.value,
            Permission.MANAGE_USERS.value,
            Permission.WORKSPACE_UPDATE.value,
            Permission.SETTINGS_UPDATE.value,
            Permission.SETTINGS_BRANDING_UPDATE.value,
            Permission.FEATURE_FLAGS_READ.value,
            Permission.FEATURE_FLAGS_MANAGE.value,
            Permission.USERS_MEMBER_LIST.value,
            Permission.USERS_MEMBER_READ.value,
            Permission.USERS_MEMBER_UPDATE_ROLE.value,
            Permission.USERS_MEMBER_SUSPEND.value,
            Permission.USERS_MEMBER_RESTORE.value,
            Permission.USERS_MEMBER_REMOVE.value,
            Permission.USERS_MEMBER_BULK.value,
            Permission.INVITATIONS_SEND.value,
            Permission.INVITATIONS_LIST.value,
            Permission.INVITATIONS_RESEND.value,
            Permission.INVITATIONS_REVOKE.value,
            Permission.ANALYTICS_EXPORT.value,
            Permission.AUDIT_LOGS_READ.value,
            Permission.AUDIT_LOGS_EXPORT.value,
            Permission.INTEGRATIONS_READ.value,
            Permission.INTEGRATIONS_CONFIGURE.value,
            Permission.BILLING_READ.value,
        }

        # Owner: Full tenant authority (Admin + Workspace deletion/archival + Billing)
        owner_perms: set[str] = set(admin_perms) | {
            Permission.WORKSPACE_DELETE.value,
            Permission.WORKSPACE_ARCHIVE.value,
            Permission.WORKSPACE_RESTORE.value,
            Permission.WORKSPACE_SUSPEND.value,
            Permission.BILLING_UPDATE.value,
            Permission.BILLING_INVOICES_READ.value,
        }

        # Platform Roles
        platform_admin_perms: set[str] = set(all_perms)
        platform_support_perms: set[str] = set(viewer_perms) | {
            Permission.AUDIT_LOGS_READ.value,
            Permission.VIEW_DETAILED_HEALTH.value,
            Permission.FEATURE_FLAGS_READ.value,
            Permission.USERS_MEMBER_LIST.value,
        }
        platform_auditor_perms: set[str] = {
            Permission.AUDIT_LOGS_READ.value,
            Permission.AUDIT_LOGS_EXPORT.value,
            Permission.ANALYTICS_READ.value,
            Permission.VIEW_DETAILED_HEALTH.value,
        }

        # Store compiled sets
        self._role_permissions[Role.VIEWER] = viewer_perms
        self._role_permissions[Role.ANALYST] = analyst_perms
        self._role_permissions[Role.MEMBER] = member_perms
        self._role_permissions[Role.ENGINEER] = engineer_perms
        self._role_permissions[Role.ADMIN] = admin_perms
        self._role_permissions[Role.OWNER] = owner_perms
        self._role_permissions[Role.PLATFORM_ADMIN] = platform_admin_perms
        self._role_permissions[Role.PLATFORM_SUPPORT] = platform_support_perms
        self._role_permissions[Role.PLATFORM_AUDITOR] = platform_auditor_perms

    def get_permissions_for_role(self, role: Role | str) -> set[str]:
        """Return all permission strings granted to a given role."""
        if isinstance(role, str):
            role = Role.from_str(role)
        return self._role_permissions.get(role, set())

    def has_permission(
        self,
        role: Role | str,
        permission: Permission | str,
        is_suspended: bool = False,
    ) -> bool:
        """Check if a given role possesses the specified permission.
        
        Suspended users receive an absolute explicit deny.
        """
        if is_suspended:
            return False

        if isinstance(role, str):
            role = Role.from_str(role)

        if role == Role.PLATFORM_ADMIN or role == Role.ADMIN or role == Role.OWNER:
            # Check direct match or admin override
            if role == Role.PLATFORM_ADMIN:
                return True

        perm_str = permission.value if isinstance(permission, Permission) else str(permission)
        return perm_str in self.get_permissions_for_role(role)


@lru_cache(maxsize=1)
def get_permission_registry() -> PermissionRegistry:
    """Return the singleton instance of the PermissionRegistry."""
    return PermissionRegistry()
