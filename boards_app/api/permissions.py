from rest_framework.permissions import BasePermission, SAFE_METHODS
from ..models import Board, Column, Task, Activity
from rest_framework import permissions
from django.shortcuts import get_object_or_404


class IsBoardMember(permissions.BasePermission):
    """
    Allow access only to authenticated users who are owner or member
    of the related board (Board, Column, Task, Activity).
    """

    def has_permission(self, request, view):
        """
        Require an authenticated user on view level.
        """
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """
        Check if the user is owner or member of the related board.
        """
       
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
    Allow DELETE on a board only for the board owner.
    For all other HTTP methods this permission does not restrict access.
    """

    def has_permission(self, request, view):
        """
        Require an authenticated user on view level.
        """
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """
        Restrict DELETE on Board instances to the board owner.
        """
        if request.method != "DELETE" or not isinstance(obj, Board):
            return True

        return obj.owner_id == request.user.id


class IsAssigneeOrReviewerForTaskWrite(BasePermission):
    """
    Allow write access on tasks only for board owner, assignee or reviewer.
    Read-only (SAFE_METHODS) is always allowed.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        """
        Restrict writes on Task instances to owner/assignee/reviewer.
        - SAFE_METHODS: always allowed.
        - DELETE: only board owner.
        - PATCH/PUT: board owner, assignee or reviewer.
        """
        if not isinstance(obj, Task):
            return True

        if request.method in SAFE_METHODS:
            return True

        user = request.user
        if not user or not user.is_authenticated:
            return False

        if request.method == "DELETE":
            return obj.board.owner_id == user.id

        return (
            obj.board.owner_id == user.id
            or obj.assignee_id == user.id
            or obj.reviewer_id == user.id
        )


class IsTaskCreatorOrBoardOwner(permissions.BasePermission):

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

