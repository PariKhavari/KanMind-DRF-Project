from boards_app.models import Board, Column, Task
from rest_framework import serializers
from django.contrib.auth.models import User
from boards_app.models import Board, Column, Task, Activity
from rest_framework.exceptions import NotFound


class UserSerializer(serializers.ModelSerializer):
    """
    Basic user serializer used in board and task APIs.
    Exposes:
    - primary key and username
    - first/last name and email
    - a computed `full_name` field
    """

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "full_name",
        ]

    def get_full_name(self, obj):
        """
        Build a display name from first_name and last_name.
        If both are empty, falls back to `username`.
        """
        full = (obj.first_name or "").strip() + " " + (obj.last_name or "").strip()
        return full.strip() or obj.username
    

class BoardListSerializer(serializers.ModelSerializer):
    """
    Serializer for board list and create responses.
    Used for:
    - GET /api/boards/
    - response of POST /api/boards/
    """

    member_count = serializers.SerializerMethodField()
    ticket_count = serializers.IntegerField(read_only=True)
    tasks_to_do_count = serializers.IntegerField(read_only=True)
    tasks_high_prio_count = serializers.IntegerField(read_only=True)
    owner_id = serializers.IntegerField( read_only=True)

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
        ]

    def get_member_count(self, obj):
        return obj.members.count()


class UserSummarySerializer(serializers.ModelSerializer):
    """
    Compact user representation used in task responses.
    Exposes:
    - id: primary key
    - email: login / contact address
    - fullname: combined first and last name or fallback to username
    """

    fullname = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "fullname"]

    def get_fullname(self, obj):
        name = (obj.first_name + " " + obj.last_name).strip()
        return name or obj.username


class TaskReadSerializer(serializers.ModelSerializer):
    """
    Read serializer for tasks:
    - used in GET /api/tasks/
    - used in GET /api/tasks/{id}/
    - used in assigned-to-me/reviewing/board-detail
    """
    board = serializers.IntegerField(source="board.id", read_only=True)
    assignee = UserSummarySerializer(read_only=True)
    reviewer = UserSummarySerializer(read_only=True)
    status = serializers.SerializerMethodField()
    priority = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(read_only=True)

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
        mapping = {
            Column.Status.TODO: "to-do",
            Column.Status.IN_PROGRESS: "in-progress",
            Column.Status.REVIEW: "review",
            Column.Status.DONE: "done",
        }
        column = getattr(obj, "column", None)
        if not column:
            return ""
        return mapping.get(column.status, "").lower()

    def get_priority(self, obj):
        return obj.priority.lower() if obj.priority else None


class TaskInBoardSerializer(TaskReadSerializer):
    """
    Task representation inside board detail responses.
    Used for:
    - GET /api/boards/{id}/ (tasks array)
    """

    class Meta(TaskReadSerializer.Meta):
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
    Detailed board representation used for GET /api/boards/{board_id}/.
    Includes:
    - id, title, owner_id
    - members: list of users assigned to the board
    - tasks: all tasks that belong to this board
    """

    owner_id = serializers.IntegerField(source="owner.id", read_only=True)
    members = UserSummarySerializer(many=True, read_only=True)
    tasks = TaskInBoardSerializer(many=True, read_only=True)

    class Meta:
        model = Board
        fields = ["id", "title", "owner_id", "members", "tasks"]


class BoardUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer used for updating a board (PATCH /api/boards/{id}/).
    Response format matches the API specification:
    - owner_data: compact representation of the board owner
    - members_data: compact representation of all board members
    - members: list of member IDs (write-only)
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
    Serializer for board columns without nested tasks.
    Used for:
    - listing columns
    - simple CRUD operations on columns
    """

    class Meta:
        model = Column
        fields = ["id", "board", "name", "status", "position"]


class TaskWriteSerializer(serializers.ModelSerializer):
    """
    Write serializer for /api/tasks/ (POST, PATCH).

    Expects:
    - board: int (board id)
    - status: "to-do" | "in-progress" | "review" | "done"
    - priority: "low" | "medium" | "high" | "critical"
    """

    board = serializers.IntegerField(write_only=True)
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

    def validate_board(self, value: int) -> Board:
        """
        Resolve integer board id to a Board instance.
        """
        try:
            return Board.objects.get(pk=value)
        except Board.DoesNotExist:
            raise NotFound("Das angegebene Board existiert nicht.")

    def _get_column_for_status(self, board: Board, status_label: str) -> Column:
        """
        Map external status label to the matching Column of the board.
        """
        label_to_choice = {
            "to-do": "TODO",
            "in-progress": "IN_PROGRESS",
            "review": "REVIEW",
            "done": "DONE",
        }
        try:
            choice_value = label_to_choice[status_label]
        except KeyError:
            raise serializers.ValidationError(
                {"status": "Ungültiger Status. Erlaubt: to-do, in-progress, review, done."}
            )

        try:
            return Column.objects.get(board=board, status=choice_value)
        except Column.DoesNotExist:
            raise serializers.ValidationError(
                {"status": "Für dieses Board existiert keine Spalte mit diesem Status."}
            )

    def _map_priority_label(self, label: str) -> str:
        """
        Map external priority label to Task.Priority value.
        """
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

    def validate(self, attrs):
        """
        For POST: status and priority are required.
        For PATCH: both may be omitted.
        """
        request = self.context.get("request")
        is_partial = getattr(request, "method", "").upper() == "PATCH"

        if not is_partial:
            if "status" not in attrs:
                raise serializers.ValidationError(
                    {"status": "Dieses Feld ist erforderlich."})
            if "priority" not in attrs:
                raise serializers.ValidationError(
                    {"priority": "Dieses Feld ist erforderlich."})

        return super().validate(attrs)

    def create(self, validated_data):
        """
        Create task: resolve status → column and priority → enum.
        """
        status_label = validated_data.pop("status")
        priority_label = validated_data.pop("priority")

        board = validated_data["board"]
        validated_data["column"] = self._get_column_for_status(
            board, status_label)
        validated_data["priority"] = self._map_priority_label(priority_label)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Update task: board stays unchanged, status/priority optional.
        """
        validated_data.pop("board", None)

        if "status" in validated_data:
            status_label = validated_data.pop("status")
            validated_data["column"] = self._get_column_for_status(
                instance.board, status_label)

        if "priority" in validated_data:
            priority_label = validated_data.pop("priority")
            validated_data["priority"] = self._map_priority_label(
                priority_label)

        return super().update(instance, validated_data)


class CommentSerializer(serializers.ModelSerializer):
    """
    - GET /api/tasks/{task_id}/comments/
    - POST /api/tasks/{task_id}/comments/
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
    Serializer for task activities/comments.
    Used for:
    - listing comments of a task
    - creating new comments
    """

    author = UserSerializer(read_only=True)

    class Meta:
        model = Activity
        fields = ["id", "task", "author", "message", "created_at"]
        read_only_fields = ["id", "created_at", "author"]
