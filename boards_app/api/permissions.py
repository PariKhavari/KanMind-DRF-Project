from rest_framework.permissions import BasePermission, SAFE_METHODS
from ..models import Board, Column, Task, Activity
from rest_framework import permissions


class IsBoardMember(permissions.BasePermission):
    """
    Zugriff nur für eingeloggte User, die Owner oder Member
    des zugehörigen Boards sind.
    Gilt für: Board, Column, Task, Activity.
    """

    def has_permission(self, request, view):
        # Auf View-Ebene: nur angemeldete User.
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Board ermitteln
        if isinstance(obj, Board):
            board = obj
        elif isinstance(obj, Column):
            board = obj.board
        elif isinstance(obj, Task):
            board = obj.board
        elif isinstance(obj, Activity):
            board = obj.task.board
        else:
            return False

        user = request.user
        if not user or not user.is_authenticated:
            return False

        if board.owner_id == user.id:
            return True

        return board.members.filter(id=user.id).exists()


class IsBoardOwnerForBoardDelete(BasePermission):
    """
    DELETE auf einem Board ist nur für den Owner erlaubt.
    Für alle anderen Methoden greift diese Permission nicht.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Nur bei DELETE auf einem Board einschränken.
        if request.method != "DELETE" or not isinstance(obj, Board):
            return True
        return obj.owner_id == request.user.id


class IsAssigneeOrReviewerForTaskWrite(BasePermission):
    """
    Schreibzugriffe auf Tasks (PATCH/PUT/DELETE) nur für
    Assignee, Reviewer oder Board-Owner.
    Lesen (SAFE_METHODS) wird nicht eingeschränkt.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Für andere Objekte nicht zuständig.
        if not isinstance(obj, Task):
            return True

        # Nur Lesen? → durchlassen.
        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user.is_authenticated:
            return False

        # Löschen: nur Owner des Boards.
        if request.method == "DELETE":
            return obj.board.owner_id == user.id

        # Patch/Put: Owner, Assignee oder Reviewer.
        return (
            obj.board.owner_id == user.id
            or obj.assignee_id == user.id
            or obj.reviewer_id == user.id
        )


class IsTaskCreatorOrBoardOwner(permissions.BasePermission):
    """
    DELETE einer Task:
    - erlaubt, wenn der User Board-Owner ODER Task-Ersteller ist.
    - für andere HTTP-Methoden (GET, PATCH, PUT) greift diese Permission nicht.
    """

    def has_object_permission(self, request, view, obj):
        if request.method != "DELETE":
            return True

        if not isinstance(obj, Task):
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        if obj.board.owner_id == user.id:
            return True

        if obj.created_by_id == user.id:
            return True

        return False

