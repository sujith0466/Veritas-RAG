"""Workspace Ownership Transfer Service.

Governed by Section 7 Batch 1 (REV5).
Implements the state machine, lock ordering (L_W -> L_TRANS -> L_WM),
authorization validation, and atomic notifications for:
- 7.1 Ownership Nomination
- 7.2 Ownership Acceptance and Rejection
- 7.3 Nomination Expiration and Cancellation
"""

from datetime import datetime, timedelta
from typing import Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.notification import (
    Notification,
    NotificationCategory,
    NotificationSeverity,
)
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_former_owner_departure import FormerOwnerDepartureType
from backend.models.entities.workspace_member import (
    MemberStatus,
    WorkspaceMember,
    WorkspaceRole,
)
from backend.models.entities.workspace_ownership_transfer import (
    DecisionStatus,
    FormerOwnerChoice,
    ReminderStatus,
    ReminderType,
    TransferStatus,
    WorkspaceOwnershipRoleReminder,
    WorkspaceOwnershipTransfer,
)
from backend.services.workspace.former_owner_departure_service import (
    FormerOwnerDepartureService,
)


class WorkspaceTransferService:
    """Service encapsulating workspace ownership transfer business logic and state machine."""

    @staticmethod
    async def _get_db_now(session: AsyncSession) -> datetime:
        """Obtain authoritative database timestamp."""
        res = await session.execute(select(func.clock_timestamp()))
        return res.scalar_one()

    @staticmethod
    async def _record_in_app_notification(
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        title: str,
        message: str,
    ) -> None:
        """Atomically persist in-app notification within current transaction."""
        ws_res = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = ws_res.scalar_one_or_none()
        tenant_id = getattr(workspace, "tenant_id", None) or workspace_id

        notif = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            category=NotificationCategory.SECURITY.value,
            severity=NotificationSeverity.INFO.value,
            title=title,
            message=message,
            action_url=f"/workspaces/{workspace_id}/members",
        )
        session.add(notif)
        await session.flush()

    async def _check_and_apply_expiration(
        self,
        session: AsyncSession,
        transfer: WorkspaceOwnershipTransfer,
        db_now: datetime,
    ) -> bool:
        """Evaluates authoritative expiration under lock.
        If expired, transitions to EXPIRED, sets expired_at = db_now,
        dispatches dual in-app notifications, and flushes.
        """
        if (
            transfer.status == TransferStatus.PENDING.value
            and db_now >= transfer.expires_at
        ):
            transfer.status = TransferStatus.EXPIRED.value
            transfer.expired_at = db_now

            await self._record_in_app_notification(
                session,
                transfer.workspace_id,
                transfer.nominated_by_user_id,
                "Ownership Nomination Expired",
                "The ownership nomination has expired because it was not accepted within 7 days.",
            )
            await self._record_in_app_notification(
                session,
                transfer.workspace_id,
                transfer.nominee_user_id,
                "Ownership Nomination Expired",
                "The ownership nomination has expired because it was not accepted within 7 days.",
            )
            await session.flush()
            return True
        return False

    async def initiate_nomination(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        current_user_id: uuid.UUID,
        nominee_user_id: uuid.UUID,
    ) -> WorkspaceOwnershipTransfer:
        """7.1 Ownership Nomination: Initiates an ownership transfer nomination."""
        if current_user_id == nominee_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot nominate self as workspace owner",
            )

        # 1. Acquire L_W (Decision D-3.1)
        ws_res = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # 2. Acquire L_TRANS (read-under-lock without mutating yet)
        trans_res = await session.execute(
            select(WorkspaceOwnershipTransfer)
            .where(
                WorkspaceOwnershipTransfer.workspace_id == workspace_id,
                WorkspaceOwnershipTransfer.status == TransferStatus.PENDING.value,
            )
            .with_for_update()
        )
        existing = trans_res.scalar_one_or_none()

        # 3. Acquire L_WM sorted by user_id (Decision D-3.5)
        member_ids = sorted([current_user_id, nominee_user_id])
        mem_res = await session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id.in_(member_ids),
                WorkspaceMember.is_deleted == False,
            )
            .order_by(WorkspaceMember.user_id)
            .with_for_update()
        )
        members = list(mem_res.scalars().all())
        member_map = {m.user_id: m for m in members}

        # In-Lock Validation 1: Verify caller authorization BEFORE any mutation or side effect
        caller_member = member_map.get(current_user_id)
        if (
            not caller_member
            or caller_member.status != MemberStatus.ACTIVE.value
            or caller_member.role != WorkspaceRole.OWNER.value
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only active workspace OWNER can initiate ownership nomination",
            )

        # In-Lock Validation 2: Verify nominee eligibility BEFORE any mutation or side effect
        nominee_member = member_map.get(nominee_user_id)
        if not nominee_member or nominee_member.status != MemberStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nominee must be an active workspace member",
            )
        if nominee_member.role not in [
            WorkspaceRole.ADMIN.value,
            WorkspaceRole.MEMBER.value,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Member with role {nominee_member.role} cannot be nominated as OWNER",
            )

        # In-Lock Evaluation: Authorization & eligibility confirmed. Now safely inspect and expire existing transfer
        db_now = await self._get_db_now(session)
        if existing:
            if db_now >= existing.expires_at:
                await self._check_and_apply_expiration(session, existing, db_now)
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A pending ownership nomination already exists for this workspace",
                )

        # 4. Fetch emails for snapshot preservation (WP 7.13)
        users_res = await session.execute(
            select(User.id, User.email).where(User.id.in_([current_user_id, nominee_user_id]))
        )
        email_map = {uid: email for uid, email in users_res.all()}
        current_owner_email = email_map.get(current_user_id, "")
        nominee_email = email_map.get(nominee_user_id, "")

        # Insert Transfer Record with consistent db_now timestamps & immutable snapshots
        transfer = WorkspaceOwnershipTransfer(
            workspace_id=workspace_id,
            nominated_by_user_id=current_user_id,
            nominee_user_id=nominee_user_id,
            status=TransferStatus.PENDING.value,
            created_at=db_now,
            expires_at=db_now + timedelta(days=7),
            current_owner_email_snapshot=current_owner_email,
            nominated_user_email_snapshot=nominee_email,
        )
        session.add(transfer)
        await session.flush()

        # 5. Transactional In-App Notification
        await self._record_in_app_notification(
            session,
            workspace_id,
            nominee_user_id,
            "Workspace Ownership Nomination",
            f"You have been nominated as Owner of workspace '{workspace.name}'. Please accept or reject within 7 days.",
        )
        await session.commit()
        await session.refresh(transfer)
        return transfer

    async def accept_transfer(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        transfer_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> WorkspaceOwnershipTransfer:
        """7.2 Ownership Acceptance: Explicit acceptance promoting nominee and demoting former owner."""
        # 1. Acquire L_W (Decision D-3.1)
        ws_res = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # 2. Acquire L_TRANS
        trans_res = await session.execute(
            select(WorkspaceOwnershipTransfer)
            .where(
                WorkspaceOwnershipTransfer.id == transfer_id,
                WorkspaceOwnershipTransfer.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        transfer = trans_res.scalar_one_or_none()
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nomination not found",
            )

        # In-Lock Validation: verify caller is designated nominee BEFORE evaluating expiration or mutating state
        if transfer.nominee_user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the designated nominee can accept this nomination",
            )
        if transfer.status != TransferStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Nomination cannot be accepted in status {transfer.status}",
            )

        # Database clock obtained under lock
        db_now = await self._get_db_now(session)
        if await self._check_and_apply_expiration(session, transfer, db_now):
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Ownership nomination has expired",
            )

        # 3. Acquire L_WM: Deterministic single-query lock on all affected member records in ascending user_id order
        aff_res = await session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                or_(
                    (WorkspaceMember.role == WorkspaceRole.OWNER.value)
                    & (WorkspaceMember.status == MemberStatus.ACTIVE.value),
                    WorkspaceMember.user_id == transfer.nominee_user_id,
                ),
                WorkspaceMember.is_deleted == False,
            )
            .order_by(WorkspaceMember.user_id)
            .with_for_update()
        )
        affected_members = list(aff_res.scalars().all())

        # Invariant 1: Exactly one active OWNER must exist currently
        active_owners = [
            m
            for m in affected_members
            if m.role == WorkspaceRole.OWNER.value
            and m.status == MemberStatus.ACTIVE.value
        ]
        if len(active_owners) != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Workspace must have exactly one active OWNER",
            )
        current_owner = active_owners[0]

        # Invariant 2: Current active OWNER must be the original nominator
        if current_owner.user_id != transfer.nominated_by_user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ownership nomination is invalidated: nominator is no longer the active workspace owner",
            )

        # Invariant 3: Nominee must still be an active ADMIN or MEMBER
        nominee_member = next(
            (m for m in affected_members if m.user_id == transfer.nominee_user_id),
            None,
        )
        if not nominee_member or nominee_member.status != MemberStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nominee membership is no longer active",
            )
        if nominee_member.role not in [
            WorkspaceRole.ADMIN.value,
            WorkspaceRole.MEMBER.value,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Nominee role {nominee_member.role} is ineligible for ownership",
            )

        # 4. Atomic Role & Status Transition with Unique Index Safeguard:
        # Step A: Demote former owner: role=MEMBER, status=TRANSFER_PENDING (zero access)
        current_owner.role = WorkspaceRole.MEMBER.value
        current_owner.status = MemberStatus.TRANSFER_PENDING.value
        current_owner.updated_at = db_now

        # Step B: Explicitly flush demotion to database to satisfy uq_workspace_members_active_owner
        # This guarantees 0 active owners exist in the DB before the nominee's promotion is issued!
        await session.flush()

        # Step C: Promote nominee: role=OWNER, status=ACTIVE
        nominee_member.role = WorkspaceRole.OWNER.value
        nominee_member.status = MemberStatus.ACTIVE.value
        nominee_member.updated_at = db_now
        await session.flush()

        # Step D: Mark transfer accepted
        transfer.status = TransferStatus.ACCEPTED.value
        transfer.responded_at = db_now

        # Batch 2: Initialize former owner choice and decision deadline (30 calendar days)
        transfer.former_owner_choice = FormerOwnerChoice.PENDING.value
        transfer.decision_status = DecisionStatus.PENDING.value
        transfer.decision_deadline_at = db_now + timedelta(days=30)

        # Batch 2: Schedule role reminders exclusively for the new owner (Days 14, 25, 29)
        r14 = WorkspaceOwnershipRoleReminder(
            transfer_id=transfer.id,
            workspace_id=workspace_id,
            recipient_user_id=transfer.nominee_user_id,
            reminder_type=ReminderType.DAY_14.value,
            scheduled_for=db_now + timedelta(days=14),
            status=ReminderStatus.PENDING.value,
            created_at=db_now,
        )
        r25 = WorkspaceOwnershipRoleReminder(
            transfer_id=transfer.id,
            workspace_id=workspace_id,
            recipient_user_id=transfer.nominee_user_id,
            reminder_type=ReminderType.DAY_25.value,
            scheduled_for=db_now + timedelta(days=25),
            status=ReminderStatus.PENDING.value,
            created_at=db_now,
        )
        r29 = WorkspaceOwnershipRoleReminder(
            transfer_id=transfer.id,
            workspace_id=workspace_id,
            recipient_user_id=transfer.nominee_user_id,
            reminder_type=ReminderType.DAY_29.value,
            scheduled_for=db_now + timedelta(days=29),
            status=ReminderStatus.PENDING.value,
            created_at=db_now,
        )
        session.add_all([r14, r25, r29])

        # 5. Dual In-App Notifications
        nominee_name = (
            getattr(nominee_member.user, "display_name", None)
            or getattr(nominee_member.user, "full_name", None)
            or "The nominee"
            if hasattr(nominee_member, "user") and nominee_member.user
            else "The nominee"
        )
        await self._record_in_app_notification(
            session,
            workspace_id,
            transfer.nominated_by_user_id,
            "Ownership Transfer Completed",
            f"{nominee_name} accepted ownership of '{workspace.name}'.",
        )
        await self._record_in_app_notification(
            session,
            workspace_id,
            transfer.nominee_user_id,
            "You are now Workspace Owner",
            f"You have assumed ownership of '{workspace.name}'.",
        )
        await session.commit()
        await session.refresh(transfer)
        return transfer

    async def reject_transfer(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        transfer_id: uuid.UUID,
        current_user_id: uuid.UUID,
        reason: Optional[str] = None,
    ) -> WorkspaceOwnershipTransfer:
        """7.2 Ownership Rejection: Nominee explicitly rejects ownership nomination."""
        # 1. Acquire L_W
        ws_res = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # 2. Acquire L_TRANS
        trans_res = await session.execute(
            select(WorkspaceOwnershipTransfer)
            .where(
                WorkspaceOwnershipTransfer.id == transfer_id,
                WorkspaceOwnershipTransfer.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        transfer = trans_res.scalar_one_or_none()
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nomination not found",
            )

        # In-Lock Validation: verify caller is designated nominee BEFORE evaluating expiration or mutating state
        if transfer.nominee_user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the designated nominee can reject this nomination",
            )
        if transfer.status != TransferStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Nomination cannot be rejected in status {transfer.status}",
            )

        # Database clock obtained under lock
        db_now = await self._get_db_now(session)
        if await self._check_and_apply_expiration(session, transfer, db_now):
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Ownership nomination has expired and cannot be rejected",
            )

        # 3. Mark transfer REJECTED
        transfer.status = TransferStatus.REJECTED.value
        transfer.rejection_reason = reason
        transfer.responded_at = db_now

        # 4. Notify nominator
        await self._record_in_app_notification(
            session,
            workspace_id,
            transfer.nominated_by_user_id,
            "Ownership Nomination Declined",
            f"Nominee declined ownership of workspace '{workspace.name}'. Reason: {reason or 'None provided'}.",
        )
        await session.commit()
        await session.refresh(transfer)
        return transfer

    async def cancel_transfer(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        transfer_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> WorkspaceOwnershipTransfer:
        """7.3 Nomination Cancellation: Active workspace OWNER cancels pending nomination."""
        # 1. Acquire L_W
        ws_res = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # 2. Acquire L_TRANS
        trans_res = await session.execute(
            select(WorkspaceOwnershipTransfer)
            .where(
                WorkspaceOwnershipTransfer.id == transfer_id,
                WorkspaceOwnershipTransfer.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        transfer = trans_res.scalar_one_or_none()
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nomination not found",
            )

        # 3. Acquire L_WM for caller
        caller_res = await session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user_id,
                WorkspaceMember.is_deleted == False,
            )
            .with_for_update()
        )
        caller_member = caller_res.scalar_one_or_none()

        # In-Lock Validation: Verify caller is active OWNER BEFORE inspecting status or mutating
        # Unauthorized callers receive HTTP 403 unconditionally, preventing status disclosure
        if (
            not caller_member
            or caller_member.status != MemberStatus.ACTIVE.value
            or caller_member.role != WorkspaceRole.OWNER.value
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the current active workspace OWNER can cancel a nomination",
            )

        # 4. Only after successful authorization, inspect transfer status
        if transfer.status != TransferStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Nomination cannot be cancelled in status {transfer.status}",
            )

        # 5. Database clock obtained under lock
        db_now = await self._get_db_now(session)
        if await self._check_and_apply_expiration(session, transfer, db_now):
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Ownership nomination has expired and cannot be cancelled",
            )

        # 6. Mark transfer CANCELLED
        transfer.status = TransferStatus.CANCELLED.value
        transfer.cancelled_at = db_now

        # 7. Notify nominee
        await self._record_in_app_notification(
            session,
            workspace_id,
            transfer.nominee_user_id,
            "Ownership Nomination Cancelled",
            f"The pending ownership nomination for '{workspace.name}' has been cancelled by the workspace owner.",
        )
        await session.commit()
        await session.refresh(transfer)
        return transfer

    async def get_active_transfer(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> Optional[WorkspaceOwnershipTransfer]:
        """Strict L_W -> L_TRANS -> L_WM Lock Hierarchy & Authorization Revalidation."""
        # 1. Acquire L_W
        ws_res = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # 2. Acquire L_TRANS
        trans_res = await session.execute(
            select(WorkspaceOwnershipTransfer)
            .where(
                WorkspaceOwnershipTransfer.workspace_id == workspace_id,
                WorkspaceOwnershipTransfer.status == TransferStatus.PENDING.value,
            )
            .with_for_update()
        )
        transfer = trans_res.scalar_one_or_none()

        # 3. Acquire L_WM to re-read and validate caller's membership under lock
        caller_res = await session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user_id,
                WorkspaceMember.is_deleted == False,
            )
            .with_for_update()
        )
        caller_member = caller_res.scalar_one_or_none()

        # Validate caller is an active workspace member
        if not caller_member or caller_member.status != MemberStatus.ACTIVE.value:
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Caller is not an active workspace member",
            )

        if not transfer:
            await session.commit()
            return None

        # Dynamic expiration check under lock
        db_now = await self._get_db_now(session)
        if await self._check_and_apply_expiration(session, transfer, db_now):
            await session.commit()
            return None

        # Determine authorization using the freshly re-validated membership state
        is_owner = caller_member.role == WorkspaceRole.OWNER.value
        is_nominee = transfer.nominee_user_id == current_user_id

        # Return transfer details ONLY to the current active OWNER or designated nominee
        if not (is_owner or is_nominee):
            await session.commit()
            return None  # Third-party active members receive null

        await session.commit()
        return transfer

    async def record_former_owner_choice(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        transfer_id: uuid.UUID,
        current_user_id: uuid.UUID,
        choice: str,
        notes: Optional[str] = None,
    ) -> WorkspaceOwnershipTransfer:
        """7.4 Former OWNER STAY/LEAVE: Records disposition choice under L_W -> L_TRANS -> L_WM."""
        choice_clean = choice.strip().upper() if choice else ""
        if choice_clean not in (FormerOwnerChoice.STAY.value, FormerOwnerChoice.LEAVE.value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid choice '{choice}'. Must be STAY or LEAVE.",
            )

        # 1. Acquire L_W
        ws_res = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # 2. Acquire L_TRANS
        trans_res = await session.execute(
            select(WorkspaceOwnershipTransfer)
            .where(
                WorkspaceOwnershipTransfer.id == transfer_id,
                WorkspaceOwnershipTransfer.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        transfer = trans_res.scalar_one_or_none()
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer nomination not found",
            )

        # In-Lock Validation 1: State must be ACCEPTED and choice must be PENDING
        if transfer.status != TransferStatus.ACCEPTED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Former owner choice cannot be recorded in transfer status {transfer.status}",
            )
        if transfer.former_owner_choice != FormerOwnerChoice.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Former owner choice has already been recorded",
            )

        # In-Lock Validation 2: Caller must be the original nominator (former owner)
        if transfer.nominated_by_user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the former workspace owner can submit this disposition choice",
            )

        # Dynamic deadline verification under DB clock
        db_now = await self._get_db_now(session)
        if transfer.decision_deadline_at and db_now >= transfer.decision_deadline_at:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Former owner choice window has expired",
            )

        # 3. Acquire L_WM for former owner
        mem_res = await session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user_id,
                WorkspaceMember.is_deleted == False,
            )
            .with_for_update()
        )
        former_member = mem_res.scalar_one_or_none()

        if choice_clean == FormerOwnerChoice.LEAVE.value:
            # State 6: FORMER_OWNER_LEAVE_DEPARTED
            transfer.former_owner_choice = FormerOwnerChoice.LEAVE.value
            transfer.former_owner_choice_at = db_now
            transfer.decision_status = DecisionStatus.DECIDED_REMOVED.value
            transfer.decided_at = db_now
            transfer.response_notes = notes

            if former_member:
                former_member.is_deleted = True
                former_member.updated_at = db_now

            # Cancel all pending role reminders
            await session.execute(
                update(WorkspaceOwnershipRoleReminder)
                .where(
                    WorkspaceOwnershipRoleReminder.transfer_id == transfer_id,
                    WorkspaceOwnershipRoleReminder.status == ReminderStatus.PENDING.value,
                )
                .values(status=ReminderStatus.CANCELLED.value)
            )

            # Record immutable departure history (WP 7.10)
            await FormerOwnerDepartureService.record_departure(
                session=session,
                workspace_id=workspace_id,
                former_owner_id=transfer.nominated_by_user_id,
                transfer_id=transfer.id,
                departure_type=FormerOwnerDepartureType.VOLUNTARY_LEAVE,
                confirmed_by_user_id=current_user_id,
                former_role="OWNER",
                retained_role=None,
                departure_notes=notes,
                confirmed_at=db_now,
            )

            # Notifications
            await self._record_in_app_notification(
                session,
                workspace_id,
                transfer.nominee_user_id,
                "Former Owner Departed",
                f"The former owner chose to leave '{workspace.name}'.",
            )
        elif choice_clean == FormerOwnerChoice.STAY.value:
            # State 7: STAY_ROLE_DECISION_PENDING
            transfer.former_owner_choice = FormerOwnerChoice.STAY.value
            transfer.former_owner_choice_at = db_now
            transfer.response_notes = notes

            # Membership remains TRANSFER_PENDING (zero workspace access)
            # Late STAY handling: Mark any reminders scheduled <= db_now as SKIPPED
            await session.execute(
                update(WorkspaceOwnershipRoleReminder)
                .where(
                    WorkspaceOwnershipRoleReminder.transfer_id == transfer_id,
                    WorkspaceOwnershipRoleReminder.status == ReminderStatus.PENDING.value,
                    WorkspaceOwnershipRoleReminder.scheduled_for <= db_now,
                )
                .values(status=ReminderStatus.SKIPPED.value)
            )

            # Notifications
            await self._record_in_app_notification(
                session,
                workspace_id,
                transfer.nominee_user_id,
                "Former Owner Chose to Stay",
                f"The former owner chose to remain in '{workspace.name}'. You may decide their role within 30 days of transfer acceptance.",
            )

        await session.flush()
        return transfer

    async def decide_former_owner_role(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        transfer_id: uuid.UUID,
        current_user_id: uuid.UUID,
        decision: str,
        notes: Optional[str] = None,
    ) -> WorkspaceOwnershipTransfer:
        """7.5 New OWNER Role Decision: Assigns ADMIN, MEMBER, or REMOVE under L_W -> L_TRANS -> L_WM."""
        decision_clean = decision.strip().upper() if decision else ""
        if decision_clean == "VIEWER":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Prohibited role: VIEWER cannot be assigned to a former owner.",
            )
        if decision_clean not in ("ADMIN", "MEMBER", "REMOVE"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid decision '{decision}'. Permitted decisions: ADMIN, MEMBER, REMOVE.",
            )

        # 1. Acquire L_W
        ws_res = await session.execute(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        workspace = ws_res.scalar_one_or_none()
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found",
            )

        # 2. Acquire L_TRANS
        trans_res = await session.execute(
            select(WorkspaceOwnershipTransfer)
            .where(
                WorkspaceOwnershipTransfer.id == transfer_id,
                WorkspaceOwnershipTransfer.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        transfer = trans_res.scalar_one_or_none()
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transfer nomination not found",
            )

        # In-Lock Validation 1: Caller must be the current active OWNER (the nominee who accepted)
        if transfer.nominee_user_id != current_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the current workspace owner can decide the former owner's role",
            )

        # In-Lock Validation 2: Transfer must be ACCEPTED, STAY chosen, and decision PENDING
        if transfer.status != TransferStatus.ACCEPTED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role decision cannot be made on transfer status {transfer.status}",
            )
        if transfer.former_owner_choice != FormerOwnerChoice.STAY.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Role decision cannot be made before the former owner explicitly selects STAY",
            )
        if transfer.decision_status != DecisionStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A role decision has already been executed for this transfer",
            )

        # Deadline check under DB clock
        db_now = await self._get_db_now(session)
        if transfer.decision_deadline_at and db_now >= transfer.decision_deadline_at:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Role decision window has expired. Automatic fallback applies.",
            )

        # 3. Acquire L_WM for former owner
        mem_res = await session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == transfer.nominated_by_user_id,
                WorkspaceMember.is_deleted == False,
            )
            .with_for_update()
        )
        former_member = mem_res.scalar_one_or_none()

        if decision_clean == "ADMIN":
            # State 8: DECIDED_ROLE_ADMIN
            transfer.decision_status = DecisionStatus.DECIDED_ADMIN.value
            transfer.decided_at = db_now
            transfer.decided_by_user_id = current_user_id
            transfer.decision_notes = notes

            if former_member:
                former_member.role = WorkspaceRole.ADMIN.value
                former_member.status = MemberStatus.ACTIVE.value
                former_member.is_former_owner = True
                former_member.updated_at = db_now

            # Record immutable departure history (WP 7.10)
            await FormerOwnerDepartureService.record_departure(
                session=session,
                workspace_id=workspace_id,
                former_owner_id=transfer.nominated_by_user_id,
                transfer_id=transfer.id,
                departure_type=FormerOwnerDepartureType.NEW_OWNER_RETAINED,
                confirmed_by_user_id=current_user_id,
                former_role="OWNER",
                retained_role=WorkspaceRole.ADMIN.value,
                departure_notes=notes,
                confirmed_at=db_now,
            )

            await self._record_in_app_notification(
                session,
                workspace_id,
                transfer.nominated_by_user_id,
                "Role Assigned: ADMIN",
                f"You have been granted the ADMIN role in '{workspace.name}'.",
            )

        elif decision_clean == "MEMBER":
            # State 9: DECIDED_ROLE_MEMBER
            transfer.decision_status = DecisionStatus.DECIDED_MEMBER.value
            transfer.decided_at = db_now
            transfer.decided_by_user_id = current_user_id
            transfer.decision_notes = notes

            if former_member:
                former_member.role = WorkspaceRole.MEMBER.value
                former_member.status = MemberStatus.ACTIVE.value
                former_member.is_former_owner = True
                former_member.updated_at = db_now

            # Record immutable departure history (WP 7.10)
            await FormerOwnerDepartureService.record_departure(
                session=session,
                workspace_id=workspace_id,
                former_owner_id=transfer.nominated_by_user_id,
                transfer_id=transfer.id,
                departure_type=FormerOwnerDepartureType.NEW_OWNER_RETAINED,
                confirmed_by_user_id=current_user_id,
                former_role="OWNER",
                retained_role=WorkspaceRole.MEMBER.value,
                departure_notes=notes,
                confirmed_at=db_now,
            )

            await self._record_in_app_notification(
                session,
                workspace_id,
                transfer.nominated_by_user_id,
                "Role Assigned: MEMBER",
                f"You have been assigned the MEMBER role in '{workspace.name}'.",
            )

        elif decision_clean == "REMOVE":
            # State 10: DECIDED_ROLE_REMOVED
            transfer.decision_status = DecisionStatus.DECIDED_REMOVED.value
            transfer.decided_at = db_now
            transfer.decided_by_user_id = current_user_id
            transfer.decision_notes = notes

            if former_member:
                former_member.is_deleted = True
                former_member.updated_at = db_now

            # Record immutable departure history (WP 7.10)
            await FormerOwnerDepartureService.record_departure(
                session=session,
                workspace_id=workspace_id,
                former_owner_id=transfer.nominated_by_user_id,
                transfer_id=transfer.id,
                departure_type=FormerOwnerDepartureType.NEW_OWNER_REMOVED,
                confirmed_by_user_id=current_user_id,
                former_role="OWNER",
                retained_role=None,
                departure_notes=notes,
                confirmed_at=db_now,
            )

            await self._record_in_app_notification(
                session,
                workspace_id,
                transfer.nominated_by_user_id,
                "Workspace Access Concluded",
                f"You have been removed from '{workspace.name}' by the workspace owner.",
            )

        # Cancel remaining pending role reminders
        await session.execute(
            update(WorkspaceOwnershipRoleReminder)
            .where(
                WorkspaceOwnershipRoleReminder.transfer_id == transfer_id,
                WorkspaceOwnershipRoleReminder.status == ReminderStatus.PENDING.value,
            )
            .values(status=ReminderStatus.CANCELLED.value)
        )

        await session.flush()
        return transfer
