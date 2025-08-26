import json

from django.core.management.base import BaseCommand

from apps.account.models import User
from apps.resume.models import Certificate, Connection, Education, Language, Project, Resume, Skill, WorkExperience
from apps.settings.models import ConnectionWay, ForeignLanguage, StudyField, University
from apps.settings.models import Skill as SettingSkill


class Command(BaseCommand):
    """We run this command in rahisho"""

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="The path to the rahzist_db.json file")

    def handle(self, *args, **kwargs):
        file_path = kwargs["file_path"]

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR("فایل یافت نشد."))
            return

        resumes = data.get("resumes", [])
        users = data.get("users", [])
        users_ids = data.get("users_ids", [])
        resumes_ids = data.get("resumes_ids", [])

        not_imported_user_list = []
        added_user_data = []
        community_managers_data = {}

        # Calculates the count of same users in rahisho and razist
        same_users_ids = []
        for user in User.objects.all():
            for user_id in users_ids:
                if user.user_info.get("id") == user_id:
                    same_users_ids.append(user_id)
        print(f"same user: {len(same_users_ids)}")
        with open("same_user_rahzist_ids.json", "w", encoding="utf-8") as json_file:
            json.dump(same_users_ids, json_file, indent=2, ensure_ascii=False)

        # Calculates the count of same resumes in rahisho and razist
        test_resume = []
        for resume in Resume.objects.all():
            for resume_id in resumes_ids:
                if resume.user.user_info.get("id") == resume_id:
                    test_resume.append(resume_id)
        print(f"same resume: {len(test_resume)}")

        # Add the users of rahzist to rahisho, if they have no account in rahisho
        for user in users:
            _user = User.objects.filter(user_info__id=user.get("user_info")["id"]).first()

            # If the exists user is a community manager in rahzist, keep it's rahzist id beside its id in rahisho
            if _user and user.get("is_community_manager"):
                community_managers_data.update({f"{str(_user.id)}": user.get("rahzist_id")})

            if not _user:
                try:
                    created_user = User.objects.create(
                        username=user.get("user_info").get("username"),
                        user_info=user.get("user_info"),
                        bio=user.get("bio"),
                        avatar=user.get("avatar"),
                        city_id=user.get("city"),
                        address=user.get("address"),
                        birth_date=(user.get("birth_date")),
                        gender=user.get("gender"),
                        military_status=user.get("military_status"),
                        marriage_status=user.get("marriage_status"),
                        # community=Community.objects.get(id=user.get("community")),
                        telegram_address=user.get("telegram_address"),
                        is_accespted_terms=user.get("is_accespted_terms"),
                    )
                    created_user.groups.add(user.get("group"))

                    # Adding the id of newly added user to a json
                    added_user_data.append(str(created_user.user_info.get("id")))
                    with open("added_user_sso_ids.json", "w", encoding="utf-8") as json_file:
                        json.dump(added_user_data, json_file, indent=2, ensure_ascii=False)

                    # If new user is a community manager in rahzist, keep it's rahzist id beside its new id in rahisho
                    if user.get("is_community_manager"):
                        community_managers_data.update({f"{str(created_user.id)}": user.get("rahzist_id")})

                        with open("rahzist_community_managers.json", "w", encoding="utf-8") as json_file:
                            json.dump(community_managers_data, json_file, indent=2, ensure_ascii=False)

                except Exception:
                    # print(str(e))
                    not_imported_user_list.append(user)

        # Add the resumes of rahzist users to rahisho, if they have no resume in rahisho
        for resume in resumes:
            user_sso_id = resume.get("user_sso_id")

            _user = User.objects.filter(user_info__id=user_sso_id).first()
            if _user and not Resume.objects.filter(user__user_info__id=user_sso_id).exists():
                _resume = Resume.objects.create(user=_user, status=resume.get("status"), steps=resume.get("steps"))

                # Education
                for education in resume.get("educations"):
                    filed = StudyField.objects.filter(title=education["field"]).first()
                    if not filed:
                        filed = StudyField.objects.create(title=education["field"])

                    university = University.objects.filter(title=education["university"]).first()
                    if not university:
                        university = University.objects.create(title=education["university"])

                    Education.objects.create(
                        resume=_resume,
                        grade=education["grade"],
                        field=filed,
                        university=university,
                        start_date=education["start_date"],
                        end_date=education["end_date"],
                    )

                # WorkExperience
                jobs = [
                    WorkExperience(
                        resume=_resume,
                        job_title=job["job_title"],
                        company_name=job["company_name"],
                        start_date=job["start_date"],
                        end_date=job["end_date"],
                    )
                    for job in resume.get("jobs")
                ]
                WorkExperience.objects.bulk_create(jobs)

                # Skill
                for skill in resume.get("skills"):
                    skill_name = SettingSkill.objects.filter(title=skill["skill_name"]).first()
                    if not skill_name:
                        skill_name = SettingSkill.objects.create(title=skill["skill_name"])

                    Skill.objects.create(resume=_resume, skill_name=skill_name, level=skill["level"])

                # Languages
                for language in resume.get("languages"):
                    language_name = ForeignLanguage.objects.filter(title=language["language_name"]).first()
                    if not language_name:
                        language_name = ForeignLanguage.objects.create(title=language["language_name"])

                    Language.objects.create(resume=_resume, language_name=language_name, level=language["level"])

                # Certificates
                certificates = [
                    Certificate(
                        resume=_resume,
                        certificate_title=certificate["certificate_title"],
                        institution=certificate["institution"],
                        issue_date=certificate["issue_date"],
                        file=certificate["file"],
                        description=certificate["description"],
                        link=certificate["link"],
                    )
                    for certificate in resume.get("certificates")
                ]
                Certificate.objects.bulk_create(certificates)

                # Connection
                for connection in resume.get("connections"):
                    title = ConnectionWay.objects.filter(title=connection["title"]).first()
                    if not title:
                        title = ConnectionWay.objects.create(title=connection["title"])

                    Connection.objects.create(
                        resume=_resume, title=title, link=connection["link"], telegram=connection["telegram"]
                    )

                # Project
                projects = [
                    Project(
                        resume=_resume,
                        title=project["title"],
                        description=project["description"],
                        start_date=project["start_date"],
                        end_date=project["end_date"],
                    )
                    for project in resume.get("resume_projects")
                ]
                Project.objects.bulk_create(projects)

        # Keep the users info that can't to be imported in rahisho in a json
        user_data = []
        for user in not_imported_user_list:
            user_data.append(
                {
                    "sso_id": user.get("user_info").get("id", None),
                    "national_id": user.get("user_info").get("national_id", None),
                    "first_name": user.get("user_info").get("first_name", None),
                    "last_name": user.get("user_info").get("last_name", None),
                    "mobile_number": user.get("user_info").get("mobile_number", None),
                }
            )
        with open("not_imported_user.json", "w", encoding="utf-8") as json_file:
            json.dump(user_data, json_file, indent=2, ensure_ascii=False)

        print("Data added successfully.")
