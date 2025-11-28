from django.db import models
from django.contrib.auth.models import User


class Board(models.Model):

    title = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,related_name="owned_boards", help_text="Eigentümer des Boards.")
    members = models.ManyToManyField(User, related_name="boards", blank=True, help_text="User, die Zugriff auf dieses Board haben.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title

    @property
    def member_count(self) -> int:
        return self.members.count()

    @property
    def ticket_count(self) -> int:
        return self.tasks.count()

    @property
    def tasks_to_do_count(self) -> int:
        return self.tasks.filter(column__status=Column.Status.TODO).count()

    @property
    def tasks_high_prio_count(self) -> int:
        return self.tasks.filter(priority=Task.Priority.HIGH).count()


class Column(models.Model):

    class Status(models.TextChoices):
        TODO = "TODO", "To Do"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        REVIEW = "REVIEW", "Review"
        DONE = "DONE", "Done"

    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name="columns")
    name = models.CharField(max_length=100, help_text="Anzeigename der Spalte, z.B. 'To Do'.")
    status = models.CharField(max_length=20, choices=Status.choices,help_text="Logischer Status der Spalte (To Do, In Progress, Review, Done).")
    position = models.PositiveIntegerField(default=0, help_text="Reihenfolge der Spalten im Board.")

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return f"{self.board.title} - {self.name}"


class Task(models.Model):

    class Priority(models.TextChoices):
        LOW = "LOW", "low"
        MEDIUM = "MEDIUM", "medium"
        HIGH = "HIGH", "high"
        CRITICAL = "CRITICAL", "critical"

    board = models.ForeignKey(Board, on_delete=models.CASCADE,related_name="tasks", help_text="Zu welchem Board gehört die Task?")
    column = models.ForeignKey(Column, on_delete=models.SET_NULL, null=True, blank=True,related_name="tasks", help_text="In welcher Spalte (Status) befindet sich die Task?")
    title = models.CharField( max_length=255,help_text="Kurzer, prägnanter Titel der Task.")
    description = models.TextField(blank=True, help_text="Ausführliche Beschreibung der Task.")
    due_date = models.DateField(null=True, blank=True, help_text="Fälligkeitsdatum der Task.")
    priority = models.CharField(max_length=10, choices=Priority.choices,help_text="Priorität der Task.")
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,related_name="assigned_tasks", help_text="Wer ist für die Umsetzung zuständig?")
    reviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,related_name="review_tasks", help_text="Wer soll die Task reviewen?")
    position = models.PositiveIntegerField(default=0, help_text="Reihenfolge innerhalb der Spalte.")
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="created_tasks",help_text="Benutzer, der diese Task erstellt hat.",)
    created_at = models.DateTimeField(auto_now_add=True, help_text="Erstellzeitpunkt der Task.")
    updated_at = models.DateTimeField(auto_now=True, help_text="Zeitpunkt der letzten Änderung.")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="Zeitpunkt, an dem die Task als Done markiert wurde.")

    class Meta:
        ordering = ["column__position", "position", "id"]

    @property
    def status(self) -> str:
        if not self.column:
            return None
        return self.column.status.label

    @property
    def comments_count(self) -> int:
        return self.activities.count()

    def __str__(self) -> str:
        return self.title


class Activity(models.Model):

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="activities",help_text="Zu welcher Task gehört diese Aktivität?")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,related_name="activities", help_text="Wer hat den Kommentar / die Aktivität erstellt?")
    message = models.TextField(help_text="Kommentar")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Wann wurde die Aktivität erstellt?")

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        author_name = self.author.username if self.author else "Unknown"
        return f"Activity by {author_name} on {self.task.title}"
