import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session, selectinload

import models
from schemas import LearningPlanAIOutput


def get_active_learning_plan(db: Session, user_id: int) -> Optional[models.LearningPlan]:
    return (
        db.query(models.LearningPlan)
        .options(
            selectinload(models.LearningPlan.generated_courses)
            .selectinload(models.GeneratedCourse.generated_modules)
            .selectinload(models.GeneratedModule.generated_lesson_plans)
        )
        .filter(models.LearningPlan.user_id == user_id, models.LearningPlan.is_active == True)
        .first()
    )


def create_learning_plan_from_ai_output(
    db: Session,
    user_id: int,
    plan_output: LearningPlanAIOutput,
) -> models.LearningPlan:
    if get_active_learning_plan(db, user_id) is not None:
        raise ValueError("User already has an active learning plan")

    generated_at = datetime.now(timezone.utc) if plan_output.status == "ready" else None
    plan = models.LearningPlan(
        user_id=user_id,
        status=plan_output.status,
        comfortable_language=plan_output.comfortable_language,
        learning_language=plan_output.learning_language,
        learner_summary=plan_output.learner_summary,
        weakest_skills=json.dumps(plan_output.weakest_skills, ensure_ascii=False),
        strongest_skills=json.dumps(plan_output.strongest_skills, ensure_ascii=False),
        generation_model=plan_output.generation_model,
        generation_version=plan_output.generation_version,
        generated_at=generated_at,
        is_active=True,
    )

    for course_output in sorted(plan_output.courses, key=lambda course: course.sequence_order):
        course = models.GeneratedCourse(
            title=course_output.title,
            description=course_output.description,
            primary_skill=course_output.primary_skill,
            difficulty=course_output.difficulty,
            sequence_order=course_output.sequence_order,
            is_unlocked=course_output.is_unlocked,
            completion_status=course_output.completion_status,
        )
        for module_output in sorted(course_output.modules, key=lambda module: module.sequence_order):
            module = models.GeneratedModule(
                title=module_output.title,
                description=module_output.description,
                sequence_order=module_output.sequence_order,
            )
            for lesson_output in sorted(module_output.lesson_plans, key=lambda lesson: lesson.sequence_order):
                module.generated_lesson_plans.append(
                    models.GeneratedLessonPlan(
                        title=lesson_output.title,
                        learning_objective=lesson_output.learning_objective,
                        skill=lesson_output.skill,
                        difficulty=lesson_output.difficulty,
                        sequence_order=lesson_output.sequence_order,
                        content_status=lesson_output.content_status,
                    )
                )
            course.generated_modules.append(module)
        plan.generated_courses.append(course)

    db.add(plan)
    db.flush()
    return plan


def learning_plan_to_response(plan: models.LearningPlan) -> dict:
    return {
        "id": plan.id,
        "user_id": plan.user_id,
        "status": plan.status,
        "comfortable_language": plan.comfortable_language,
        "learning_language": plan.learning_language,
        "learner_summary": plan.learner_summary,
        "weakest_skills": json.loads(plan.weakest_skills or "[]"),
        "strongest_skills": json.loads(plan.strongest_skills or "[]"),
        "generation_model": plan.generation_model,
        "generation_version": plan.generation_version,
        "is_active": plan.is_active,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "generated_at": plan.generated_at,
        "courses": [
            {
                "id": course.id,
                "learning_plan_id": course.learning_plan_id,
                "title": course.title,
                "description": course.description,
                "primary_skill": course.primary_skill,
                "difficulty": course.difficulty,
                "sequence_order": course.sequence_order,
                "is_unlocked": course.is_unlocked,
                "completion_status": course.completion_status,
                "modules": [
                    {
                        "id": module.id,
                        "generated_course_id": module.generated_course_id,
                        "title": module.title,
                        "description": module.description,
                        "sequence_order": module.sequence_order,
                        "lesson_plans": [
                            {
                                "id": lesson.id,
                                "generated_module_id": lesson.generated_module_id,
                                "title": lesson.title,
                                "learning_objective": lesson.learning_objective,
                                "skill": lesson.skill,
                                "difficulty": lesson.difficulty,
                                "sequence_order": lesson.sequence_order,
                                "content_status": lesson.content_status,
                            }
                            for lesson in module.generated_lesson_plans
                        ],
                    }
                    for module in course.generated_modules
                ],
            }
            for course in plan.generated_courses
        ],
    }
