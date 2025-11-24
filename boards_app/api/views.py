from datetime import timedelta
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets, permissions,status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from boards_app.models import Board, Column, Task, Activity
from .serializers import (
    BoardListSerializer,
    BoardDetailSerializer,
    BoardUpdateSerializer,
    ColumnSerializer,
    TaskReadSerializer,
    TaskWriteSerializer,
    CommentSerializer,
    ActivitySerializer,
)
from .permissions import (
    IsBoardMember,
    IsBoardOwnerForBoardDelete,
    IsAssigneeOrReviewerForTaskWrite,
    IsTaskCreatorOrBoardOwner
)


class BoardViewSet(viewsets.ModelViewSet):
    """
    CRUD für Boards:
    - GET    /api/boards/        → Liste (BoardListSerializer)
    - POST   /api/boards/        → erstellen (BoardListSerializer als Response)
    - GET    /api/boards/{id}/   → Detail (BoardDetailSerializer)
    - PATCH  /api/boards/{id}/   → aktualisieren (BoardUpdateSerializer)
    - DELETE /api/boards/{id}/   → löschen
    """
    permission_classes = [permissions.IsAuthenticated,IsBoardMember,IsBoardOwnerForBoardDelete,]

    def get_queryset(self):
        """
        Nur Boards, in denen der aktuelle User Member ist.
        (Wenn du Owner auch einbeziehen willst: Q(owner=user) dazu nehmen.)
        """
        user = self.request.user
        return Board.objects.filter(Q(owner=user) | Q(members=user)).distinct()

    def get_serializer_class(self):
        if self.action in ["list", "create"]:
            return BoardListSerializer
        if self.action == "retrieve":
            return BoardDetailSerializer
        if self.action in ["update", "partial_update"]:
            return BoardUpdateSerializer
        return BoardListSerializer
    
    def create(self, request, *args, **kwargs):
        write_serializer = TaskWriteSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        write_serializer.is_valid(raise_exception=True)

        # HIER: created_by auf den aktuellen User setzen
        task = write_serializer.save(created_by=request.user)

        read_serializer = TaskReadSerializer(
            task,
            context=self.get_serializer_context(),
        )
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)   

    def perform_create(self, serializer):
        """
        Beim Erstellen: Owner = aktueller User,
        und sich selbst als Member hinzufügen.
        """
        board = serializer.save(owner=self.request.user)
        board.members.add(self.request.user)


class ColumnViewSet(viewsets.ModelViewSet):
    """
    CRUD für Columns (Spalten).
    Nur Columns aus Boards, in denen der User Mitglied ist.
    """
    serializer_class = ColumnSerializer
    permission_classes = [permissions.IsAuthenticated, IsBoardMember]

    def get_queryset(self):
        user = self.request.user
        return Column.objects.filter(board__members=user).distinct()


class TaskViewSet(viewsets.ModelViewSet):
    """
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
        """Tasks aus Boards, bei denen der User Owner oder Mitglied ist."""
        user = self.request.user
        return Task.objects.filter(
            Q(board__owner=user) | Q(board__members=user)
        ).distinct()

    def get_serializer_class(self):
        """Write-Serializer für POST/PATCH, Read-Serializer für GET."""
        if self.action in ["create", "update", "partial_update"]:
            return TaskWriteSerializer
        return TaskReadSerializer


    def _ensure_user_is_board_member(self, board: Board):
        """
        Wirft 403, wenn der aktuelle User kein Member/Owner des Boards ist.
        """
        user = self.request.user

        if board.owner_id == user.id:
            return

        if board.members.filter(id=user.id).exists():
            return
        raise PermissionDenied("Der Benutzer muss Mitglied des Boards sein, um eine Task zu erstellen.")

    def create(self, request, *args, **kwargs):
        """
        POST /api/tasks/
        - validiert mit TaskWriteSerializer
        - prüft Board-Mitgliedschaft
        - speichert Task mit created_by=request.user
        - Antwort mit TaskReadSerializer (voller Datensatz)
        """
        write_serializer = TaskWriteSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        write_serializer.is_valid(raise_exception=True)

        board = write_serializer.validated_data.get("board")
        if board is None:
            # Sollte durch DRF schon abgefangen sein, aber zur Sicherheit:
            raise PermissionDenied("Ein Board muss angegeben werden, um eine Task zu erstellen.")

        # hier wird die Vorgabe erzwungen:
        self._ensure_user_is_board_member(board)

        task = write_serializer.save(created_by=request.user)

        read_serializer = TaskReadSerializer(
            task,
            context=self.get_serializer_context(),
        )
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        """
        PUT/PATCH /api/tasks/{id}/
        - benutzt WriteSerializer für Eingabe
        - Antwort mit ReadSerializer
        Board-Mitgliedschaft wird über IsBoardMember geprüft.
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
        return Response(read_serializer.data)


class ActivityViewSet(viewsets.ModelViewSet):
    
    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticated, IsBoardMember]

    def get_queryset(self):
        user = self.request.user
        return Activity.objects.filter(task__board__members=user).distinct()


class DashboardStatsView(APIView):
    """Liefert Kennzahlen für das persönliche Dashboard des Users."""
    permission_classes = [permissions.IsAuthenticated]

    def _get_boards_count(self, user):
        """Anzahl Boards, in denen der User Mitglied ist."""
        return Board.objects.filter(members=user).distinct().count()

    def _get_my_tasks_qs(self, user):
        """Tasks, die dem User zugewiesen sind und in seinen Boards liegen."""
        return Task.objects.filter(
            assignee=user,
            board__members=user,
        ).distinct()

    def _get_urgent_tasks_count(self, tasks_qs):
        """Dringende To-do-Tasks (high/critical, fällig in 7 Tagen)."""
        today = timezone.now().date()
        upcoming = today + timedelta(days=7)
        return tasks_qs.filter(
            column__status=Column.Status.TODO,
            priority__in=[Task.Priority.HIGH, Task.Priority.CRITICAL],
            due_date__range=(today, upcoming),
        ).count()

    def _get_done_recent_count(self, tasks_qs):
        """Tasks im Status Done der letzten 14 Tage."""
        two_weeks_ago = timezone.now() - timedelta(days=14)
        return tasks_qs.filter(
            column__status=Column.Status.DONE,
            completed_at__gte=two_weeks_ago,
        ).count()

    def get(self, request, format=None):
        """Gibt die Dashboard-Statistiken für den aktuellen User zurück."""
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
    Tasks, bei denen der aktuelle User Assignee ist.
    """
    serializer_class = TaskReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Task.objects.filter(assignee=user).order_by("due_date", "id")


class ReviewingTasksView(generics.ListAPIView):
    """
    Liefert alle Tasks, bei denen der aktuelle User als Reviewer eingetragen ist.
    """
    serializer_class = TaskReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Task.objects.filter(reviewer=user).order_by("due_date", "id")


class TaskCommentsListCreateView(generics.ListCreateAPIView):
    """
    GET /api/tasks/{task_id}/comments/
    POST /api/tasks/{task_id}/comments/
    """
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_task(self):
        task_id = self.kwargs["task_id"]
        task = get_object_or_404(Task, pk=task_id)
        user = self.request.user
        # nur Boards, in denen der User Member/Owner ist
        if not (task.board.owner_id == user.id or task.board.members.filter(id=user.id).exists()):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Du bist kein Mitglied dieses Boards.")
        return task

    def get_queryset(self):
        task = self.get_task()
        return Activity.objects.filter(task=task).order_by("created_at")

    def perform_create(self, serializer):
        task = self.get_task()
        serializer.save(task=task, author=self.request.user)


class TaskCommentDeleteView(generics.DestroyAPIView):
    """
    DELETE /api/tasks/{task_id}/comments/{comment_id}/
    Nur der Autor des Kommentars darf löschen.
    """
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "comment_id"

    def get_queryset(self):
        user = self.request.user
        task_id = self.kwargs["task_id"]
        # nur Kommentare an der Task, bei denen der aktuelle User Autor ist
        return Activity.objects.filter(task_id=task_id, author=user)
