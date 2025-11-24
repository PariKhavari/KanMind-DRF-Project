from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BoardViewSet,
    TaskViewSet,
    ColumnViewSet,
    AssignedToMeTasksView,
    ReviewingTasksView,
    TaskCommentsListCreateView,
    TaskCommentDeleteView,
    DashboardStatsView,
)

router = DefaultRouter()
router.register("boards", BoardViewSet, basename="board")
router.register("tasks", TaskViewSet, basename="task")
router.register("columns", ColumnViewSet, basename="column")

urlpatterns = [
    # ⇨ SPEZIELLE TASK-ENDPOINTS MÜSSEN VOR DEM ROUTER STEHEN
    path("tasks/assigned-to-me/", AssignedToMeTasksView.as_view(), name="tasks-assigned-to-me"),
    path("tasks/reviewing/", ReviewingTasksView.as_view(), name="tasks-reviewing"),

    path("tasks/<int:task_id>/comments/", TaskCommentsListCreateView.as_view(), name="task-comments"),
    path("tasks/<int:task_id>/comments/<int:comment_id>/", TaskCommentDeleteView.as_view(), name="task-comment-delete"),

    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),

    # Router ganz zum Schluss:
    path("", include(router.urls)),
]

