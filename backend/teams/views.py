from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsClubAdmin, IsUnionAdmin
from accounts.rbac import get_user_clubs, get_user_union_workspaces

from .models import (
    PlayerRegistration,
    PlayerTransfer,
    Squad,
    SquadMember,
    SquadSubmission,
    StaffMember,
    Team,
)
from .serializers import (
    PlayerRegistrationSerializer,
    PlayerRegistrationSummarySerializer,
    PlayerTransferSerializer,
    PlayerTransferSummarySerializer,
    SquadMemberSerializer,
    SquadSerializer,
    SquadSubmissionSerializer,
    SquadSubmissionSummarySerializer,
    StaffMemberSerializer,
    StaffMemberSummarySerializer,
    TeamSerializer,
)

# ---------------------------------------------------------------------------
# TEAMS CRUD
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsClubAdmin])
def team_list_create_view(request):
    """
    GET: List teams for clubs the user manages.
    POST: Create a new team.
    """
    user_clubs = get_user_clubs(request.user)

    if request.method == "GET":
        queryset = Team.objects.filter(club__in=user_clubs).select_related("club")
        serializer = TeamSerializer(queryset, many=True)
        return Response(serializer.data)

    # POST
    serializer = TeamSerializer(data=request.data)
    if serializer.is_valid():
        club = serializer.validated_data["club"]
        if club not in user_clubs:
            return Response(
                {"detail": "You do not have permission to create teams for this club."},
                status=status.HTTP_403_FORBIDDEN,
            )
        team = serializer.save()
        return Response(TeamSerializer(team).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsClubAdmin])
def team_detail_view(request, pk):
    """
    GET: Retrieve a team.
    PUT/PATCH: Update a team.
    DELETE: Delete a team.
    """
    try:
        team = Team.objects.get(pk=pk)
    except Team.DoesNotExist:
        return Response({"detail": "Team not found."}, status=status.HTTP_404_NOT_FOUND)

    user_clubs = get_user_clubs(request.user)
    if team.club not in user_clubs:
        return Response(
            {"detail": "You do not have permission to manage this team."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        serializer = TeamSerializer(team)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = TeamSerializer(team, data=request.data, partial=partial)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(TeamSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    team.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# SQUADS CRUD
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsClubAdmin])
def squad_list_create_view(request):
    """
    GET: List squads for teams in clubs the user manages.
    POST: Create a new squad.
    """
    user_clubs = get_user_clubs(request.user)

    if request.method == "GET":
        queryset = Squad.objects.filter(team__club__in=user_clubs).select_related(
            "team", "team__club", "competition"
        )
        serializer = SquadSerializer(queryset, many=True)
        return Response(serializer.data)

    # POST
    serializer = SquadSerializer(data=request.data)
    if serializer.is_valid():
        team = serializer.validated_data["team"]
        if team.club not in user_clubs:
            return Response(
                {
                    "detail": "You do not have permission to create squads for this team."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        squad = serializer.save()
        return Response(SquadSerializer(squad).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsClubAdmin])
def squad_detail_view(request, pk):
    """
    GET: Retrieve a squad.
    PUT/PATCH: Update a squad.
    DELETE: Delete a squad.
    """
    try:
        squad = Squad.objects.get(pk=pk)
    except Squad.DoesNotExist:
        return Response(
            {"detail": "Squad not found."}, status=status.HTTP_404_NOT_FOUND
        )

    user_clubs = get_user_clubs(request.user)
    if squad.team.club not in user_clubs:
        return Response(
            {"detail": "You do not have permission to manage this squad."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        serializer = SquadSerializer(squad)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = SquadSerializer(squad, data=request.data, partial=partial)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(SquadSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    squad.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# SQUAD MEMBERS
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsClubAdmin])
def squad_member_list_create_view(request, squad_pk):
    """
    GET: List members of a squad.
    POST: Add a player to a squad.
    """
    try:
        squad = Squad.objects.get(pk=squad_pk)
    except Squad.DoesNotExist:
        return Response(
            {"detail": "Squad not found."}, status=status.HTTP_404_NOT_FOUND
        )

    user_clubs = get_user_clubs(request.user)
    if squad.team.club not in user_clubs:
        return Response(
            {"detail": "You do not have permission to manage this squad."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        queryset = SquadMember.objects.filter(squad=squad).select_related("player")
        serializer = SquadMemberSerializer(queryset, many=True)
        return Response(serializer.data)

    # POST
    serializer = SquadMemberSerializer(data=request.data)
    if serializer.is_valid():
        member_squad = serializer.validated_data["squad"]
        if member_squad.id != squad.id:
            return Response(
                {"detail": "Player must be added to the specified squad."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        member = serializer.save()
        return Response(
            SquadMemberSerializer(member).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsClubAdmin])
def squad_member_detail_view(request, squad_pk, pk):
    """
    GET: Retrieve a squad member.
    PUT/PATCH: Update a squad member.
    DELETE: Remove a player from a squad.
    """
    try:
        squad = Squad.objects.get(pk=squad_pk)
        member = SquadMember.objects.get(pk=pk, squad=squad)
    except Squad.DoesNotExist:
        return Response(
            {"detail": "Squad not found."}, status=status.HTTP_404_NOT_FOUND
        )
    except SquadMember.DoesNotExist:
        return Response(
            {"detail": "Squad member not found."}, status=status.HTTP_404_NOT_FOUND
        )

    user_clubs = get_user_clubs(request.user)
    if squad.team.club not in user_clubs:
        return Response(
            {"detail": "You do not have permission to manage this squad."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        serializer = SquadMemberSerializer(member)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = SquadMemberSerializer(member, data=request.data, partial=partial)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(SquadMemberSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    member.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# PLAYER REGISTRATIONS
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsClubAdmin])
def player_registration_list_create_view(request):
    """
    GET: List player registrations for clubs the user manages.
    POST: Register a new player.
    """
    user_clubs = get_user_clubs(request.user)

    if request.method == "GET":
        queryset = PlayerRegistration.objects.filter(
            club__in=user_clubs
        ).select_related("club", "team", "user")
        serializer = PlayerRegistrationSummarySerializer(queryset, many=True)
        return Response(serializer.data)

    # POST
    serializer = PlayerRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        club = serializer.validated_data["club"]
        if club not in user_clubs:
            return Response(
                {
                    "detail": "You do not have permission to register players for this club."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        player = serializer.save()
        return Response(
            PlayerRegistrationSerializer(player).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsClubAdmin])
def player_registration_detail_view(request, pk):
    """
    GET: Retrieve a player registration.
    PUT/PATCH: Update a player registration.
    DELETE: Delete a player registration.
    """
    try:
        player = PlayerRegistration.objects.get(pk=pk)
    except PlayerRegistration.DoesNotExist:
        return Response(
            {"detail": "Player registration not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    user_clubs = get_user_clubs(request.user)
    if player.club not in user_clubs:
        return Response(
            {
                "detail": "You do not have permission to manage this player registration."
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        serializer = PlayerRegistrationSerializer(player)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = PlayerRegistrationSerializer(
            player, data=request.data, partial=partial
        )
        if serializer.is_valid():
            updated = serializer.save()
            return Response(PlayerRegistrationSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    player.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# STAFF MEMBERS
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsClubAdmin])
def staff_member_list_create_view(request):
    """
    GET: List staff members for clubs the user manages.
    POST: Add a new staff member.
    """
    user_clubs = get_user_clubs(request.user)

    if request.method == "GET":
        queryset = StaffMember.objects.filter(club__in=user_clubs).select_related(
            "club", "team", "user"
        )
        serializer = StaffMemberSummarySerializer(queryset, many=True)
        return Response(serializer.data)

    # POST
    serializer = StaffMemberSerializer(data=request.data)
    if serializer.is_valid():
        club = serializer.validated_data["club"]
        if club not in user_clubs:
            return Response(
                {"detail": "You do not have permission to add staff to this club."},
                status=status.HTTP_403_FORBIDDEN,
            )
        staff = serializer.save()
        return Response(
            StaffMemberSerializer(staff).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsClubAdmin])
def staff_member_detail_view(request, pk):
    """
    GET: Retrieve a staff member.
    PUT/PATCH: Update a staff member.
    DELETE: Delete a staff member.
    """
    try:
        staff = StaffMember.objects.get(pk=pk)
    except StaffMember.DoesNotExist:
        return Response(
            {"detail": "Staff member not found."}, status=status.HTTP_404_NOT_FOUND
        )

    user_clubs = get_user_clubs(request.user)
    if staff.club not in user_clubs:
        return Response(
            {"detail": "You do not have permission to manage this staff member."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        serializer = StaffMemberSerializer(staff)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = StaffMemberSerializer(staff, data=request.data, partial=partial)
        if serializer.is_valid():
            updated = serializer.save()
            return Response(StaffMemberSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    staff.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# PLAYER TRANSFERS
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsClubAdmin])
def player_transfer_list_create_view(request):
    """
    GET: List transfers involving clubs the user manages.
    POST: Initiate a player transfer.
    """
    user_clubs = get_user_clubs(request.user)

    if request.method == "GET":
        queryset = PlayerTransfer.objects.filter(
            Q(from_club__in=user_clubs) | Q(to_club__in=user_clubs)
        ).select_related("player", "from_club", "to_club", "requested_by")
        serializer = PlayerTransferSummarySerializer(queryset, many=True)
        return Response(serializer.data)

    # POST
    serializer = PlayerTransferSerializer(data=request.data)
    if serializer.is_valid():
        from_club = serializer.validated_data["from_club"]
        to_club = serializer.validated_data["to_club"]
        if from_club not in user_clubs and to_club not in user_clubs:
            return Response(
                {
                    "detail": "You do not have permission to initiate transfers for these clubs."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        # Auto-generate transfer number
        import uuid

        transfer_number = f"TRF-{uuid.uuid4().hex[:8].upper()}"
        transfer = serializer.save(
            requested_by=request.user,
            transfer_number=transfer_number,
        )
        return Response(
            PlayerTransferSerializer(transfer).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsClubAdmin])
def player_transfer_detail_view(request, pk):
    """
    GET: Retrieve a transfer.
    PUT/PATCH: Update a transfer.
    DELETE: Cancel a transfer.
    """
    try:
        transfer = PlayerTransfer.objects.get(pk=pk)
    except PlayerTransfer.DoesNotExist:
        return Response(
            {"detail": "Transfer not found."}, status=status.HTTP_404_NOT_FOUND
        )

    user_clubs = get_user_clubs(request.user)
    if transfer.from_club not in user_clubs and transfer.to_club not in user_clubs:
        return Response(
            {"detail": "You do not have permission to manage this transfer."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        serializer = PlayerTransferSerializer(transfer)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = PlayerTransferSerializer(
            transfer, data=request.data, partial=partial
        )
        if serializer.is_valid():
            updated = serializer.save()
            return Response(PlayerTransferSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if transfer.status in (PlayerTransfer.TransferStatus.PENDING,):
        transfer.status = PlayerTransfer.TransferStatus.CANCELLED
        transfer.save(update_fields=["status"])
    return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# SQUAD SUBMISSIONS
# ---------------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsClubAdmin])
def squad_submission_list_create_view(request):
    """
    GET: List squad submissions for clubs the user manages.
    POST: Submit a squad for approval.
    """
    user_clubs = get_user_clubs(request.user)

    if request.method == "GET":
        queryset = SquadSubmission.objects.filter(
            squad__team__club__in=user_clubs
        ).select_related("squad", "submitted_by", "reviewed_by")
        serializer = SquadSubmissionSummarySerializer(queryset, many=True)
        return Response(serializer.data)

    # POST - Submit a squad
    serializer = SquadSubmissionSerializer(data=request.data)
    if serializer.is_valid():
        squad = serializer.validated_data["squad"]
        if squad.team.club not in user_clubs:
            return Response(
                {
                    "detail": "You do not have permission to submit squads for this club."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        # Auto-generate submission number
        import uuid

        submission_number = f"SUB-{uuid.uuid4().hex[:8].upper()}"
        submission = serializer.save(
            submitted_by=request.user,
            submission_number=submission_number,
        )
        # Update squad status
        squad.status = Squad.SquadStatus.SUBMITTED
        squad.submitted_at = timezone.now()
        squad.submitted_by = request.user
        squad.save(update_fields=["status", "submitted_at", "submitted_by"])
        return Response(
            SquadSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsClubAdmin])
def squad_submission_detail_view(request, pk):
    """
    GET: Retrieve a squad submission.
    PUT/PATCH: Update a squad submission.
    DELETE: Delete a squad submission (only drafts).
    """
    try:
        submission = SquadSubmission.objects.get(pk=pk)
    except SquadSubmission.DoesNotExist:
        return Response(
            {"detail": "Squad submission not found."}, status=status.HTTP_404_NOT_FOUND
        )

    user_clubs = get_user_clubs(request.user)
    if submission.squad.team.club not in user_clubs:
        return Response(
            {"detail": "You do not have permission to manage this squad submission."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "GET":
        serializer = SquadSubmissionSerializer(submission)
        return Response(serializer.data)

    if request.method in ("PUT", "PATCH"):
        partial = request.method == "PATCH"
        serializer = SquadSubmissionSerializer(
            submission, data=request.data, partial=partial
        )
        if serializer.is_valid():
            updated = serializer.save()
            return Response(SquadSubmissionSerializer(updated).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if submission.status == SquadSubmission.SubmissionStatus.DRAFT:
        submission.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(
        {"detail": "Only draft submissions can be deleted."},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ---------------------------------------------------------------------------
# UNION ACTIONS: Review squad submissions
# ---------------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsUnionAdmin])
def squad_submission_review_view(request, pk):
    """
    POST: Approve or reject a squad submission (union admin only).
    """
    try:
        submission = SquadSubmission.objects.get(pk=pk)
    except SquadSubmission.DoesNotExist:
        return Response(
            {"detail": "Squad submission not found."}, status=status.HTTP_404_NOT_FOUND
        )

    action = request.data.get("action")
    if action not in ("approve", "reject"):
        return Response(
            {"detail": "Invalid action. Use 'approve' or 'reject'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user_workspaces = get_user_union_workspaces(request.user)
    competition = submission.squad.competition
    league = competition.league

    # Check if user has access to this league/union
    has_access = False
    for workspace in user_workspaces:
        if workspace.related_union and league.union_id == workspace.related_union_id:
            has_access = True
            break
        if (
            workspace.workspace_type == "COMMUNITY_LEAGUE"
            and league.name == workspace.name
        ):
            has_access = True
            break

    if not has_access:
        return Response(
            {"detail": "You do not have permission to review this submission."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if submission.status != SquadSubmission.SubmissionStatus.SUBMITTED:
        return Response(
            {
                "detail": f"Submission is already {submission.status}. Only SUBMITTED submissions can be reviewed."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if action == "approve":
        submission.status = SquadSubmission.SubmissionStatus.APPROVED
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        # Update squad status
        squad = submission.squad
        squad.status = Squad.SquadStatus.APPROVED
        squad.approved_at = timezone.now()
        squad.approved_by = request.user
        squad.save(update_fields=["status", "approved_at", "approved_by"])

        return Response(
            {
                "detail": "Squad submission approved successfully.",
                "submission": SquadSubmissionSerializer(submission).data,
            }
        )

    # Reject
    rejection_reason = request.data.get("rejection_reason", "")
    if not rejection_reason:
        return Response(
            {"detail": "rejection_reason is required when rejecting."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    submission.status = SquadSubmission.SubmissionStatus.REJECTED
    submission.reviewed_by = request.user
    submission.reviewed_at = timezone.now()
    submission.rejection_reason = rejection_reason
    submission.save(
        update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"]
    )

    squad = submission.squad
    squad.status = Squad.SquadStatus.REJECTED
    squad.rejection_reason = rejection_reason
    squad.save(update_fields=["status", "rejection_reason"])

    return Response(
        {
            "detail": "Squad submission rejected.",
            "submission": SquadSubmissionSerializer(submission).data,
        }
    )
