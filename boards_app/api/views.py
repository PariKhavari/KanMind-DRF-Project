from datetime import timedelta
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from boards_app.models import Board, Column, Task, Activity
from .serializers import (
    BoardDetailSerializer,
    ColumnSerializer,
    TaskReadSerializer,
    TaskWriteSerializer,
    CommentSerializer,
    ActivitySerializer,
    BoardListSerializer,
    BoardUpdateSerializer,

)
from .permissions import (
    IsBoardMember,
    IsBoardOwnerForBoardDelete,
    IsTaskCreatorOrBoardOwner
)


class BoardViewSet(viewsets.ModelViewSet):
    """
    ViewSet for board CRUD operations.
    Endpoints:
    - GET    /api/boards/        -> list  (BoardListSerializer)
    - POST   /api/boards/        -> create (BoardListSerializer response)
    - GET    /api/boards/{id}/   -> detail (BoardDetailSerializer)
    - PATCH  /api/boards/{id}/   -> update (BoardUpdateSerializer)
    - DELETE /api/boards/{id}/   -> delete (only owner)
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsBoardMember,
        IsBoardOwnerForBoardDelete,
    ]

    def get_queryset(self):
        """
        Return boards visible to the current user.
        - list: only boards where the user is owner or member
        - detail: all boards, object permissions handle 403 vs 404
        """
        if self.action == "list":
            user = self.request.user
            return Board.objects.filter(
                Q(owner=user) | Q(members=user)
            ).distinct()
        return Board.objects.all()

    def get_object(self):
        """
        Return a single board instance and enforce object-level permissions.
        """
        obj = get_object_or_404(Board, pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, obj)
        return obj

    def get_serializer_class(self):
        """
        Select serializer depending on the current action.
        """
        if self.action == "retrieve":
            return BoardDetailSerializer
        if self.action in ["update", "partial_update"]:
            return BoardUpdateSerializer
        return BoardListSerializer

    def perform_create(self, serializer):
        """
        Create a board, set the current user as owner and member,
        and create default columns for the board.
        """
        user = self.request.user
        board = serializer.save(owner=user)
        board.members.add(user)

        default_columns = [
            ("To-do",       Column.Status.TODO,        1),
            ("In-progress", Column.Status.IN_PROGRESS, 2),
            ("Review",      Column.Status.REVIEW,      3),
            ("Done",        Column.Status.DONE,        4),
        ]

        for name, status, position in default_columns:
            Column.objects.create(
                board=board,
                name=name,
                status=status,
                position=position,
            )


class ColumnViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CRUD operations on board columns.
    """

    serializer_class = ColumnSerializer
    permission_classes = [permissions.IsAuthenticated, IsBoardMember]

    def get_queryset(self):
        """
        Return columns for boards where the user is owner or member.
        """
        user = self.request.user
        return Column.objects.filter(
            Q(board__owner=user) | Q(board__members=user)
        ).distinct()


class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet for task CRUD operations.
    Endpoints:
    - GET    /api/tasks/
    - POST   /api/tasks/
    - GET    /api/tasks/{id}/
    - PATCH  /api/tasks/{id}/
    - DELETE /api/tasks/{id}/
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsBoardMember,
        IsTaskCreatorOrBoardOwner,
    ]

    def get_queryset(self):
        """
        Return tasks visible to the current user.
        * For list: only tasks on boards where the user is owner or member.
        * For detail: all tasks, permission is enforced via object permissions.
        """
        if self.action == "list":
            user = self.request.user
            return Task.objects.filter(
                Q(board__owner=user) | Q(board__members=user)
            ).distinct()
        return Task.objects.all()

    def get_object(self):
        """
        Return a single task instance and enforce object-level permissions.
        """
        obj = get_object_or_404(Task, pk=self.kwargs["pk"])
        self.check_object_permissions(self.request, obj)
        return obj

    def get_serializer_class(self):
        """
        Use write serializer for mutations, read serializer for read-only actions.
        """
        if self.action in ["create", "update", "partial_update"]:
            return TaskWriteSerializer
        return TaskReadSerializer

    def _ensure_user_is_board_member(self, board: Board):
        """
        Ensure current user is owner or member of the given board.
        :raises PermissionDenied: if the user is not allowed to create a task on this board.
        """
        user = self.request.user

        if board.owner_id == user.id:
            return

        if board.members.filter(id=user.id).exists():
            return

        raise PermissionDenied(
            "Der Benutzer muss Mitglied des Boards sein, um eine Task zu erstellen."
        )

    def create(self, request, *args, **kwargs):
        """
        Handle POST /api/tasks/.
        Validates input with TaskWriteSerializer, checks board membership
        and returns the created task using TaskReadSerializer.
        """
        write_serializer = TaskWriteSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        write_serializer.is_valid(raise_exception=True)

        board = write_serializer.validated_data.get("board")
        if board is None:
            raise PermissionDenied(
                "Ein Board muss angegeben werden, um eine Task zu erstellen."
            )

        self._ensure_user_is_board_member(board)

        task = write_serializer.save(created_by=request.user)

        read_serializer = TaskReadSerializer(
            task,
            context=self.get_serializer_context(),
        )
        headers = self.get_success_headers(read_serializer.data)
        return Response(
            read_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        """
        Handle PUT/PATCH /api/tasks/{id}/.
        Uses TaskWriteSerializer for input and TaskReadSerializer for output.
        For PATCH responses, ``board`` and ``comments_count`` are removed
        to match the API specification.
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        write_serializer = TaskWriteSerializer(
            instance,
            data=request.data,
            partial=partial,
            context=self.get_serializer_context(),
        )
        write_serializer.is_valid(raise_exception=True)
        task = write_serializer.save()

        read_serializer = TaskReadSerializer(
            task,
            context=self.get_serializer_context(),
        )
        data = dict(read_serializer.data)

        if partial:
            data.pop("board", None)
            data.pop("comments_count", None)

        return Response(data)


class ActivityViewSet(viewsets.ModelViewSet):

    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticated, IsBoardMember]

    def get_queryset(self):
        user = self.request.user
        return Activity.objects.filter(task__board__members=user).distinct()


class DashboardStatsView(APIView):
    """
    Return statistics for the user's personal dashboard.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_boards_count(self, user):
        """
        Return number of boards where the user is a member.
        """
        return Board.objects.filter(members=user).distinct().count()

    def _get_my_tasks_qs(self, user):
        """
        Return tasks assigned to the user on boards they are a member of.
        """
        return Task.objects.filter(
            assignee=user,
            board__members=user,
        ).distinct()

    def _get_urgent_tasks_count(self, tasks_qs):
        """
        Return count of urgent to-do tasks (high/critical, due in 7 days).
        """
        today = timezone.now().date()
        upcoming = today + timedelta(days=7)
        return tasks_qs.filter(
            column__status=Column.Status.TODO,
            priority__in=[Task.Priority.HIGH, Task.Priority.CRITICAL],
            due_date__range=(today, upcoming),
        ).count()

    def _get_done_recent_count(self, tasks_qs):
        """
        Return count of tasks done in the last 14 days.
        """
        two_weeks_ago = timezone.now() - timedelta(days=14)
        return tasks_qs.filter(
            column__status=Column.Status.DONE,
            completed_at__gte=two_weeks_ago,
        ).count()

    def get(self, request, format=None):
        """
        Handle GET /api/dashboard-stats/ and return user statistics.
        """
        user = request.user
        my_tasks_qs = self._get_my_tasks_qs(user)

        data = {
            "boards_member_of": self._get_boards_count(user),
            "tasks_assigned_to_me": my_tasks_qs.count(),
            "urgent_tasks_count": self._get_urgent_tasks_count(my_tasks_qs),
            "done_last_14_days": self._get_done_recent_count(my_tasks_qs),
        }
        return Response(data)


class AssignedToMeTasksView(generics.ListAPIView):
    """
    List tasks where the current user is the assignee.
    """
    serializer_class = TaskReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Task.objects.filter(assignee=user).order_by("due_date", "id")


class ReviewingTasksView(generics.ListAPIView):
    """
    List tasks where the current user is the reviewer.
    """
    serializer_class = TaskReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Task.objects.filter(reviewer=user).order_by("due_date", "id")


class TaskCommentsListCreateView(generics.ListCreateAPIView):
    """
    List and create comments for a given task.
    Endpoints:
    - GET  /api/tasks/{task_id}/comments/
    - POST /api/tasks/{task_id}/comments/
    """

    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_task(self):
        """
        Return the task for the given URL kwarg and enforce board membership.
        """
        task_id = self.kwargs["task_id"]
        task = get_object_or_404(Task, pk=task_id)
        user = self.request.user

        if not (
            task.board.owner_id == user.id
            or task.board.members.filter(id=user.id).exists()
        ):
            raise PermissionDenied("Du bist kein Mitglied dieses Boards.")

        return task

    def get_queryset(self):
        """
        Return all comments for the current task ordered by creation time.
        """
        task = self.get_task()
        return Activity.objects.filter(task=task).order_by("created_at")

    def perform_create(self, serializer):
        """
        Create a new comment for the current task and set the author.
        """
        task = self.get_task()
        serializer.save(task=task, author=self.request.user)


class TaskCommentDeleteView(generics.DestroyAPIView):
    """
    Delete a single comment of a task.
    Endpoint:
    - DELETE /api/tasks/{task_id}/comments/{comment_id}/
    """

    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "comment_id"

    def get_queryset(self):
        """
        Restrict queryset to comments of the given task.
        """
        task_id = self.kwargs["task_id"]
        return Activity.objects.filter(task_id=task_id)

    def perform_destroy(self, instance):
        """
        Allow deletion only for the author of the comment.
        """
        user = self.request.user
        if instance.author_id != user.id:
            raise PermissionDenied("Nur der Autor darf diesen Kommentar löschen.")
        return super().perform_destroy(instance)
