from boards_app.models import Board, Column, Task
from rest_framework import serializers
from django.contrib.auth.models import User
from boards_app.models import Board, Column, Task, Activity


class UserSerializer(serializers.ModelSerializer):

    # Vereinfachte Darstellung des Users für Assignee, Reviewer und Members.
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "first_name",
                  "last_name", "email", "full_name"]

    def get_full_name(self, obj):
        # Kombiniert Vor- und Nachnamen, fällt zurück auf username
        full = (obj.first_name or "").strip() + \
            " " + (obj.last_name or "").strip()
        return full.strip() or obj.username


class BoardListSerializer(serializers.ModelSerializer):
    """
    Für:
    - GET /api/boards/
    - Response von POST /api/boards/
    Felder laut Doku:
    id, title, member_count, ticket_count, tasks_to_do_count,
    tasks_high_prio_count, owner_id
    """
    member_count = serializers.IntegerField(read_only=True)
    ticket_count = serializers.IntegerField(read_only=True)
    tasks_to_do_count = serializers.IntegerField(read_only=True)
    tasks_high_prio_count = serializers.IntegerField(read_only=True)
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)

    class Meta:
        model = Board
        fields = [
            "id",
            "title",
            "member_count",
            "ticket_count",
            "tasks_to_do_count",
            "tasks_high_prio_count",
            "owner_id",
            "members",          # für Request-Body beim POST
        ]
        extra_kwargs = {
            "members": {"write_only": True, "required": False},
        }


class UserSummarySerializer(serializers.ModelSerializer):
    fullname = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "fullname"]

    def get_fullname(self, obj):
        name = (obj.first_name + " " + obj.last_name).strip()
        return name or obj.username


class TaskInBoardSerializer(serializers.ModelSerializer):
    """
    Task-Darstellung, wie sie im Board-Detail vorkommt.
    (ohne board-Feld, da Task innerhalb des Boards liegt)
    """
    assignee = UserSummarySerializer(read_only=True)
    reviewer = UserSummarySerializer(read_only=True)
    status = serializers.CharField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "assignee",
            "reviewer",
            "due_date",
            "comments_count",
        ]


class BoardDetailSerializer(serializers.ModelSerializer):
    """
    Für:
    - GET /api/boards/{board_id}/
    Felder laut Doku:
    id, title, owner_id, members[], tasks[]
    """
    owner_id = serializers.IntegerField(source="owner.id", read_only=True)
    members = UserSummarySerializer(many=True, read_only=True)
    tasks = TaskInBoardSerializer(many=True, read_only=True)

    class Meta:
        model = Board
        fields = ["id", "title", "owner_id", "members", "tasks"]


class BoardUpdateSerializer(serializers.ModelSerializer):
    """
    Für:
    - PATCH /api/boards/{board_id}/
    Response laut Doku:
    id, title, owner_data {..}, members_data [...]
    """
    owner_data = UserSummarySerializer(source="owner", read_only=True)
    members_data = UserSummarySerializer(
        source="members", many=True, read_only=True)

    class Meta:
        model = Board
        fields = ["id", "title", "owner_data", "members_data", "members"]
        extra_kwargs = {
            "members": {"write_only": True, "required": False},
        }


class ColumnSerializer(serializers.ModelSerializer):
    """
    Serializer für eine Column / Spalte ohne verschachtelte Tasks.
    Gut für einfache Endpunkte (z.B. Column-Liste).
    """

    class Meta:
        model = Column
        fields = ["id", "board", "name", "status", "position"]


class TaskReadSerializer(serializers.ModelSerializer):
    board = serializers.IntegerField(source="board.id", read_only=True)
    assignee = UserSummarySerializer(read_only=True)
    reviewer = UserSummarySerializer(read_only=True)

    # Status aus der Column holen und in "to-do", "review", ... umwandeln
    status = serializers.SerializerMethodField()
    # Priority in kleinem String zurückgeben (low/medium/high/critical)
    priority = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "board",
            "title",
            "description",
            "status",
            "priority",
            "assignee",
            "reviewer",
            "due_date",
            "comments_count",
        ]

    def get_status(self, obj):
        if obj.column is None:
            return None

        mapping = {
            Column.Status.TODO: "to-do",
            Column.Status.IN_PROGRESS: "in-progress",
            Column.Status.REVIEW: "review",
            Column.Status.DONE: "done",
        }
        return mapping.get(obj.column.status)

    def get_priority(self, obj):
        # Task.Priority speichert "LOW", "MEDIUM", ...
        mapping = {
            Task.Priority.LOW: "low",
            Task.Priority.MEDIUM: "medium",
            Task.Priority.HIGH: "high",
            Task.Priority.CRITICAL: "critical",
        }
        return mapping.get(obj.priority)

    def get_comments_count(self, obj):
        # falls dein related_name = "activities" ist
        return obj.activities.count()


class TaskWriteSerializer(serializers.ModelSerializer):
    """
    Serializer für POST/PATCH /api/tasks/

    Erwartet laut Doku u.a.:
    - status: "to-do" | "in-progress" | "review" | "done"
    - priority: "low" | "medium" | "high" | "critical"

    Bei POST müssen status + priority vorhanden sein.
    Bei PATCH dürfen Felder weggelassen werden.
    """

    # bei PATCH optional, bei POST prüfen wir das manuell
    status = serializers.CharField(write_only=True, required=False)
    priority = serializers.CharField(write_only=True, required=False)

    assignee_id = serializers.PrimaryKeyRelatedField(
        source="assignee",
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    reviewer_id = serializers.PrimaryKeyRelatedField(
        source="reviewer",
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "board",
            "title",
            "description",
            "status",
            "priority",
            "assignee_id",
            "reviewer_id",
            "due_date",
        ]
        read_only_fields = ["id"]

    # ---------- Hilfsfunktionen ----------

    def _get_column_for_status(self, board: Board, status_label: str) -> Column:
        """Mappt 'to-do' etc. auf Column.Status.* und holt die passende Spalte."""
        label_to_choice = {
            "to-do": Column.Status.TODO,
            "in-progress": Column.Status.IN_PROGRESS,
            "review": Column.Status.REVIEW,
            "done": Column.Status.DONE,
        }
        try:
            choice_value = label_to_choice[status_label]
        except KeyError:
            raise serializers.ValidationError(
                {"status": "Ungültiger Status-Wert. Erlaubt: to-do, in-progress, review, done."}
            )

        try:
            return Column.objects.get(board=board, status=choice_value)
        except Column.DoesNotExist:
            raise serializers.ValidationError(
                {"status": "Für dieses Board existiert keine Spalte mit diesem Status."}
            )

    def _map_priority_label(self, label: str) -> str:
        """Nimmt 'low'/'medium'/'high'/'critical' und liefert die DB-Werte."""
        mapping = {
            "low": Task.Priority.LOW,
            "medium": Task.Priority.MEDIUM,
            "high": Task.Priority.HIGH,
            "critical": Task.Priority.CRITICAL,
        }
        try:
            return mapping[label.lower()]
        except KeyError:
            raise serializers.ValidationError(
                {"priority": "Ungültige Priorität. Erlaubt: low, medium, high, critical."}
            )

    # ---------- create / update ----------

    def validate(self, attrs):
        """
        Bei POST: status + priority zwingend.
        Bei PATCH (partial) dürfen sie fehlen.
        """
        request = self.context.get("request")
        is_partial = getattr(request, "method", "").upper() in ["PATCH"]

        if not is_partial:
            # POST oder PUT → beide Felder müssen da sein
            if "status" not in attrs:
                raise serializers.ValidationError({"status": "Dieses Feld ist erforderlich."})
            if "priority" not in attrs:
                raise serializers.ValidationError({"priority": "Dieses Feld ist erforderlich."})

        return super().validate(attrs)

    def create(self, validated_data):
        status_label = validated_data.pop("status")
        priority_label = validated_data.pop("priority")

        board = validated_data["board"]
        validated_data["column"] = self._get_column_for_status(board, status_label)
        validated_data["priority"] = self._map_priority_label(priority_label)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Board darf laut Doku nicht geändert werden
        validated_data.pop("board", None)

        # Status nur ändern, wenn er im PATCH-Body enthalten ist
        if "status" in validated_data:
            status_label = validated_data.pop("status")
            validated_data["column"] = self._get_column_for_status(
                instance.board,
                status_label,
            )

        # Priority nur ändern, wenn im Body enthalten
        if "priority" in validated_data:
            priority_label = validated_data.pop("priority")
            validated_data["priority"] = self._map_priority_label(priority_label)

        return super().update(instance, validated_data)



class CommentSerializer(serializers.ModelSerializer):
    """
    Für:
    - GET /api/tasks/{task_id}/comments/
    - POST /api/tasks/{task_id}/comments/
    Response-Felder: id, created_at, author (Name), content
    """
    author = serializers.SerializerMethodField()
    content = serializers.CharField(source="message")

    class Meta:
        model = Activity
        fields = ["id", "created_at", "author", "content"]
        read_only_fields = ["id", "created_at", "author"]

    def get_author(self, obj):
        if obj.author is None:
            return "Unknown"
        name = (obj.author.first_name + " " + obj.author.last_name).strip()
        return name or obj.author.username


class ActivitySerializer(serializers.ModelSerializer):
    """
    Kommentare / Aktivitäten zu einer Task.
    - author: als verschachtelter User (nur lesen)
    - author_id: optional, falls du irgendwann IDs direkt setzen willst
    """

    author = UserSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = ["id", "task", "author", "message", "created_at"]
        read_only_fields = ["id", "created_at", "author"]
