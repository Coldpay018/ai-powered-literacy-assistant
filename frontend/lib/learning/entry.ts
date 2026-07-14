import type { CourseDetail, CourseLessonSummary, ProgressRecord } from "./types";

function compareCourseLessons(left: CourseLessonSummary, right: CourseLessonSummary) {
  return (
    left.sequence_order - right.sequence_order ||
    left.title.localeCompare(right.title) ||
    left.id - right.id
  );
}

function getProgressStatus(record?: ProgressRecord | null) {
  return record?.status || record?.completion_status || "not_started";
}

function isCompleted(record?: ProgressRecord | null) {
  return getProgressStatus(record) === "completed";
}

function isInProgress(record?: ProgressRecord | null) {
  return getProgressStatus(record) === "in_progress";
}

function getProgressSortValue(record?: ProgressRecord | null) {
  return record?.last_accessed_at
    ? Date.parse(record.last_accessed_at) || 0
    : record?.completed_at
      ? Date.parse(record.completed_at) || 0
      : 0;
}

export function flattenCourseLessons(course: CourseDetail) {
  if (course.lessons.length) {
    return [...course.lessons];
  }

  const orderedModules = [...course.modules].sort(
    (left, right) => left.sequence_order - right.sequence_order || left.title.localeCompare(right.title),
  );
  const flattened: CourseLessonSummary[] = [];

  for (const courseModule of orderedModules) {
    flattened.push(...[...courseModule.lessons].sort(compareCourseLessons));
  }

  return flattened;
}

export function resolveMostRecentInProgressLessonId(progressRecords: ProgressRecord[]) {
  const inProgress = progressRecords
    .filter((record) => isInProgress(record))
    .sort((left, right) => getProgressSortValue(right) - getProgressSortValue(left) || right.lesson_id - left.lesson_id);

  return inProgress[0]?.lesson_id ?? null;
}

export function resolveCourseEntryLessonId(course: CourseDetail, progressRecords: ProgressRecord[]) {
  const orderedLessons = flattenCourseLessons(course);
  if (!orderedLessons.length) {
    return null;
  }

  const progressByLessonId = new Map<number, ProgressRecord>();
  for (const record of progressRecords) {
    progressByLessonId.set(record.lesson_id, record);
  }

  const courseProgress = orderedLessons
    .map((lesson) => progressByLessonId.get(lesson.id))
    .filter((record): record is ProgressRecord => Boolean(record));

  const mostRecentInProgress = courseProgress
    .filter((record) => isInProgress(record))
    .sort((left, right) => getProgressSortValue(right) - getProgressSortValue(left) || right.lesson_id - left.lesson_id)[0];

  if (mostRecentInProgress) {
    return mostRecentInProgress.lesson_id;
  }

  let previousLessonCompleted = true;

  for (const lesson of orderedLessons) {
    const progress = progressByLessonId.get(lesson.id);
    if (previousLessonCompleted && !isCompleted(progress)) {
      return lesson.id;
    }
    previousLessonCompleted = isCompleted(progress);
  }

  const completedLessons = orderedLessons
    .map((lesson) => progressByLessonId.get(lesson.id))
    .filter((record): record is ProgressRecord => isCompleted(record));

  if (completedLessons.length) {
    const mostRecentCompleted = completedLessons.sort(
      (left, right) => getProgressSortValue(right) - getProgressSortValue(left) || right.lesson_id - left.lesson_id,
    )[0];
    return mostRecentCompleted.lesson_id;
  }

  return orderedLessons[0]?.id ?? null;
}
