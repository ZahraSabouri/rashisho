from rest_framework.response import Response
from rest_framework.views import APIView

from apps.api.permissions import IsSysgod, IsUser
from apps.exam.models import GeneralExam, UserAnswer
from apps.project.models import FinalRepresentation, ProjectAllocation
from apps.project.services import is_team_member, user_team
from apps.resume.models import Resume


class UserProfileProcess(APIView):
    permission_classes = [IsSysgod | IsUser]

    def _user(self):
        return self.request.user

    def get(self, request):
        """Shows user state in all sections."""

        resume: Resume = Resume.objects.filter(user=self._user()).first()
        user_answer, _ = UserAnswer.objects.get_or_create(user=self._user())
        project_priority: ProjectAllocation = ProjectAllocation.objects.filter(user=self._user()).first()
        project_allocation = project_priority.project if project_priority else None
        final_rep: FinalRepresentation = FinalRepresentation.objects.filter(user=self._user()).first()
        general_exams = GeneralExam.objects.all().values_list("id", flat=True)
        answer = user_answer.answer["general"]["answers"]
        general_exam = [
            {
                "exam_id": i,
                "exam_title": GeneralExam.objects.get(id=i).title,
                "status": answer[f"{i}"]["status"] if answer.get(f"{i}", None) else None,
            }
            for i in general_exams
        ]

        result = {
            "resume_completed": resume.resume_completed if resume else False,
            "resume_steps": resume.steps if resume else None,
            "belbin_exam": user_answer.answer["belbin"]["status"] == "finished" if user_answer else False,
            "general_exam": general_exam,
            "neo_exam": user_answer.answer["neo"]["status"] == "finished" if user_answer else False,
            "project_priority": project_priority.priority_selected if project_priority else False,
            "project_allocation": bool(project_allocation),
            "project_name": project_allocation.title if project_allocation else None,
            "project_telegram": project_allocation.telegram_id if project_allocation else None,
            "team": is_team_member(self._user()),
            "team_name": user_team(self._user()),
            "final_representation": final_rep.has_representation if final_rep else False,
        }
        return Response(result)
