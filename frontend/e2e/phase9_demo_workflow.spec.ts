import { expect, test } from '@playwright/test';

const DEMO_USER = {
  id: 'aaaa1111-1111-1111-1111-111111111111',
  email: 'grace.hopper@university.edu',
  full_name: 'Grace Hopper',
  is_active: true,
  created_at: '2026-11-04T12:00:00Z',
  updated_at: '2026-11-04T12:00:00Z',
};

const DEMO_COURSE_ID = 'bbbb2222-2222-2222-2222-222222222222';
const DEMO_DOC_ID = 'cccc3333-3333-3333-3333-333333333333';
const DEMO_CONCEPT_ID = 'dddd4444-4444-4444-4444-444444444444';
const DEMO_SESSION_ID = 'eeee5555-5555-5555-5555-555555555555';

test('Phase 9 reproducible 10-step student demonstration workflow', async ({ page }) => {
  const courses: Record<string, unknown>[] = [];
  const documents: Record<string, unknown>[] = [];
  let attemptsCount = 0;
  let masteryScore = 0;
  let masteryStatus = 'NOT_STARTED';
  let evidenceStatus = 'NO_EVIDENCE';

  const activity1 = {
    id: 'act-1111',
    session_id: DEMO_SESSION_ID,
    concept_id: DEMO_CONCEPT_ID,
    activity_type: 'DIAGNOSTIC_QUESTION',
    difficulty: 'INTERMEDIATE',
    prompt_text: 'How do randomized election timeouts prevent indefinite split votes in Raft?',
    status: 'ACTIVE',
    order_index: 0,
    relevant_pages: [1, 2],
    source_excerpts: [
      {
        document_id: DEMO_DOC_ID,
        filename: 'raft-consensus-lecture.pdf',
        page_start: 1,
        page_end: 2,
        section_title: '1. Raft Leader Election',
        excerpt:
          'Randomized election timeouts (150ms–300ms) ensure one candidate requests votes before others time out.',
      },
    ],
    hints_used: [] as string[],
    total_hints_available: 3,
    explanation_requested: null,
    attempts: [] as unknown[],
    created_at: '2026-11-04T12:05:00Z',
  };

  const activity2 = {
    id: 'act-2222',
    session_id: DEMO_SESSION_ID,
    concept_id: DEMO_CONCEPT_ID,
    activity_type: 'HARDER_PRACTICE',
    difficulty: 'ADVANCED',
    prompt_text:
      'Suppose a network partition isolates the old Raft leader while the majority partition elects a new leader in term T+1. Why can the old leader never commit new log entries?',
    status: 'ACTIVE',
    order_index: 1,
    relevant_pages: [2],
    source_excerpts: [
      {
        document_id: DEMO_DOC_ID,
        filename: 'raft-consensus-lecture.pdf',
        page_start: 2,
        page_end: 2,
        section_title: '2. Log Replication and Safety',
        excerpt:
          'A log entry is committed only when replicated on a majority quorum of servers in the current term.',
      },
    ],
    hints_used: [] as string[],
    total_hints_available: 3,
    explanation_requested: null,
    attempts: [] as unknown[],
    created_at: '2026-11-04T12:08:00Z',
  };

  const coachRecommendation = {
    recommended_activity: 'HARDER_PRACTICE',
    target_concept_id: DEMO_CONCEPT_ID,
    target_concept_title: 'Raft Leader Election & Quorum Safety',
    difficulty: 'ADVANCED',
    reason:
      'Independent correct answer demonstrated clear command of randomized election timeouts; advancing to harder practice on quorum safety.',
    requires_student_confirmation: false,
    policy_rule_applied: 'INDEPENDENT_SUCCESS_ADVANCE_DIFFICULTY',
    evidence_status: 'EMERGING_EVIDENCE',
    uncertainty_score: 0.22,
    alternative_activities: [
      {
        activity_type: 'TRANSFER_QUESTION',
        label: 'Transfer Question',
        difficulty: 'ADVANCED',
        description: 'Apply Raft quorum rules to a cross-datacenter scenario.',
      },
    ],
  };

  let sessionState: Record<string, unknown> = {
    id: DEMO_SESSION_ID,
    user_id: DEMO_USER.id,
    course_id: DEMO_COURSE_ID,
    course_title: 'CS-401 Distributed Systems',
    current_concept_id: DEMO_CONCEPT_ID,
    concept_title: 'Raft Leader Election & Quorum Safety',
    concept_summary: 'Randomized election timeouts, term numbers, and majority quorum safety.',
    learning_goal: 'Master Raft Leader Election & Quorum Safety',
    state: 'ACTIVE',
    started_at: '2026-11-04T12:05:00Z',
    updated_at: '2026-11-04T12:05:00Z',
    completed_at: null,
    current_activity: activity1,
    activity_history: [activity1],
    progress: {
      total_activities_generated: 1,
      completed_activities_count: 0,
      current_activity_index: 1,
      total_attempts_submitted: 0,
      hints_used_count: 0,
      explanations_requested_count: 0,
      current_difficulty: 'INTERMEDIATE',
      average_score: null,
    },
    coach_recommendation: null,
    summary: null,
  };

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname;
    const method = req.method();

    if (path === '/api/v1/auth/register' && method === 'POST') {
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'demo-token-grace',
          token_type: 'bearer',
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          user: DEMO_USER,
        }),
      });
    }

    if (path === '/api/v1/courses' && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(courses),
      });
    }

    if (path === '/api/v1/courses' && method === 'POST') {
      const body = JSON.parse(req.postData() || '{}');
      const created = {
        id: DEMO_COURSE_ID,
        user_id: DEMO_USER.id,
        title: body.title,
        code: body.code || 'CS-401',
        description: body.description || null,
        document_count: 0,
        created_at: '2026-11-04T12:01:00Z',
        updated_at: '2026-11-04T12:01:00Z',
      };
      courses.push(created);
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(created),
      });
    }

    if (path === `/api/v1/courses/${DEMO_COURSE_ID}` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ...(courses[0] || {
            id: DEMO_COURSE_ID,
            user_id: DEMO_USER.id,
            title: 'CS-401 Distributed Systems',
            code: 'CS-401',
            description: 'Consensus and replication.',
          }),
          document_count: documents.length,
        }),
      });
    }

    if (path === `/api/v1/courses/${DEMO_COURSE_ID}/documents` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(documents),
      });
    }

    if (path === `/api/v1/courses/${DEMO_COURSE_ID}/documents` && method === 'POST') {
      const uploaded = {
        id: DEMO_DOC_ID,
        user_id: DEMO_USER.id,
        course_id: DEMO_COURSE_ID,
        filename: 'raft-consensus-lecture.pdf',
        file_path: 'storage/raft-consensus-lecture.pdf',
        file_size_bytes: 98304,
        mime_type: 'application/pdf',
        page_count: 2,
        chunk_count: 2,
        status: 'READY',
        error_message: null,
        extraction_warnings: [],
        created_at: '2026-11-04T12:02:00Z',
        updated_at: '2026-11-04T12:02:00Z',
      };
      documents.push(uploaded);
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(uploaded),
      });
    }

    if (path === `/api/v1/courses/${DEMO_COURSE_ID}/concepts` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: DEMO_CONCEPT_ID,
            course_id: DEMO_COURSE_ID,
            source_document_id: DEMO_DOC_ID,
            title: 'Raft Leader Election & Quorum Safety',
            summary: 'Randomized election timeouts, term numbers, and majority quorum safety.',
            difficulty: 'INTERMEDIATE',
            display_order: 1,
            source_pages: [1, 2],
            created_at: '2026-11-04T12:02:00Z',
            updated_at: '2026-11-04T12:02:00Z',
          },
        ]),
      });
    }

    if (path === `/api/v1/courses/${DEMO_COURSE_ID}/sessions` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(attemptsCount > 0 ? [sessionState] : []),
      });
    }

    if (path === '/api/v1/sessions' && method === 'POST') {
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(sessionState),
      });
    }

    if (path === `/api/v1/sessions/${DEMO_SESSION_ID}` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(sessionState),
      });
    }

    if (path === `/api/v1/sessions/${DEMO_SESSION_ID}/submit-answer` && method === 'POST') {
      attemptsCount = 1;
      masteryScore = 76;
      masteryStatus = 'LEARNING';
      evidenceStatus = 'EMERGING_EVIDENCE';
      const attempt = {
        id: 'att-demo-1',
        activity_id: activity1.id,
        user_id: DEMO_USER.id,
        attempt_number: 1,
        response_text:
          'Raft uses randomized election timeouts (150ms–300ms) so one follower times out first, requests votes, and wins a majority before split votes occur.',
        time_spent_seconds: 20,
        submitted_at: '2026-11-04T12:06:00Z',
        created_at: '2026-11-04T12:06:00Z',
      };
      const evaluation = {
        id: 'eval-demo-1',
        attempt_id: 'att-demo-1',
        concept_id: DEMO_CONCEPT_ID,
        verdict: 'CORRECT',
        rubric_score: 0.95,
        total_score: 95,
        max_score: 100,
        passed: true,
        criteria_scores_json: [
          {
            criterion_id: 'c1',
            name: 'Randomized Election Timeouts',
            awarded_points: 100,
            max_points: 100,
            matched_ideas: ['randomized election timeouts', 'majority'],
            missing_ideas: [],
            feedback: 'Accurately explained symmetry breaking via randomized timeouts.',
          },
        ],
        strengths_json: ['Clear explanation of randomized election timeouts and majority votes'],
        strengths: ['Clear explanation of randomized election timeouts and majority votes'],
        gaps_json: [],
        gaps: [],
        misconception: null,
        evidence_json: ['randomized election timeouts (150ms–300ms)'],
        evidence: ['randomized election timeouts (150ms–300ms)'],
        confidence: 0.94,
        next_activity: 'HARDER_PRACTICE',
        error_classification: 'NONE',
        uncertain_evaluation: false,
        prompt_version: 'assessment-v1.0.0',
        overall_feedback:
          'Excellent reasoning! Randomized election timeouts prevent simultaneous candidacies and split votes.',
        evaluator_model: 'deterministic+llm',
        coach_action: 'ADVANCE',
        evaluated_at: '2026-11-04T12:06:00Z',
        created_at: '2026-11-04T12:06:00Z',
      };
      const completedAct1 = {
        ...activity1,
        status: 'COMPLETED',
        attempts: [{ attempt, evaluation }],
      };
      sessionState = {
        ...sessionState,
        state: 'FEEDBACK_READY',
        current_activity: completedAct1,
        activity_history: [completedAct1],
        coach_recommendation: coachRecommendation,
        progress: {
          total_activities_generated: 1,
          completed_activities_count: 1,
          current_activity_index: 1,
          total_attempts_submitted: 1,
          hints_used_count: 0,
          explanations_requested_count: 0,
          current_difficulty: 'INTERMEDIATE',
          average_score: 95,
        },
      };
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session: sessionState,
          attempt,
          evaluation,
          coach_recommendation: coachRecommendation,
          duplicate_prevented: false,
        }),
      });
    }

    if (path === `/api/v1/sessions/${DEMO_SESSION_ID}/next-activity` && method === 'POST') {
      const prevHistory = sessionState.activity_history as unknown[];
      sessionState = {
        ...sessionState,
        state: 'ACTIVE',
        current_activity: activity2,
        activity_history: [...prevHistory, activity2],
        progress: {
          total_activities_generated: 2,
          completed_activities_count: 1,
          current_activity_index: 2,
          total_attempts_submitted: 1,
          hints_used_count: 0,
          explanations_requested_count: 0,
          current_difficulty: 'ADVANCED',
          average_score: 95,
        },
      };
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(sessionState),
      });
    }

    if (path === `/api/v1/courses/${DEMO_COURSE_ID}/learning-profile` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: DEMO_USER.id,
          course_id: DEMO_COURSE_ID,
          course_title: 'CS-401 Distributed Systems',
          total_concepts: 1,
          mastered_concepts_count: 0,
          learning_concepts_count: attemptsCount > 0 ? 1 : 0,
          needs_review_concepts_count: 0,
          not_started_concepts_count: attemptsCount > 0 ? 0 : 1,
          overall_mastery_score: masteryScore,
          overall_uncertainty_score: 0.22,
          observed_strengths:
            attemptsCount > 0
              ? ['Clear explanation of randomized election timeouts and majority votes']
              : [],
          areas_needing_practice: [],
          recommended_next_action: coachRecommendation,
          concepts: [
            {
              concept_id: DEMO_CONCEPT_ID,
              course_id: DEMO_COURSE_ID,
              title: 'Raft Leader Election & Quorum Safety',
              summary: 'Randomized election timeouts, term numbers, and majority quorum safety.',
              display_order: 1,
              source_pages: [1, 2],
              prerequisite_concept_ids: [],
              mastery_score: masteryScore,
              mastery_status: masteryStatus,
              evidence_status: evidenceStatus,
              uncertainty_score: 0.22,
              attempts_count: attemptsCount,
              correct_attempts_count: attemptsCount,
              independent_success_count: attemptsCount,
              assisted_success_count: 0,
              last_score: attemptsCount > 0 ? 95 : null,
              last_practiced_at: attemptsCount > 0 ? '2026-11-04T12:06:00Z' : null,
              next_review_at: '2026-11-06T12:06:00Z',
              observed_strengths:
                attemptsCount > 0
                  ? ['Clear explanation of randomized election timeouts and majority votes']
                  : [],
              areas_needing_practice: [],
              recent_evidence:
                attemptsCount > 0
                  ? [
                      {
                        id: 'ev-demo-1',
                        user_id: DEMO_USER.id,
                        concept_id: DEMO_CONCEPT_ID,
                        evaluation_id: 'eval-demo-1',
                        evidence_type: 'INDEPENDENT_SUCCESS',
                        score_delta: 76,
                        observed_score: 95,
                        summary: 'Independent correct explanation of Raft election timeouts.',
                        metadata_json: {},
                        created_at: '2026-11-04T12:06:00Z',
                      },
                    ]
                  : [],
              recommended_next_action: coachRecommendation,
            },
          ],
          concept_map: [],
          recent_activity: [],
          revision_recommendations: [],
        }),
      });
    }

    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  // STEP 1: Register
  await page.goto('/#/register');
  await page.getByLabel('Full name').fill(DEMO_USER.full_name);
  await page.getByLabel('University email').fill(DEMO_USER.email);
  await page.getByLabel('Password', { exact: true }).fill('DemoPassword123!');
  await page.getByLabel('Confirm password').fill('DemoPassword123!');
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: /Welcome back, Grace/i })).toBeVisible();

  // STEP 2: Create course
  await page.getByLabel(/Course Title/i).fill('CS-401 Distributed Systems');
  await page.getByRole('button', { name: /Create Course/i }).click();
  await expect(page.getByRole('heading', { name: 'CS-401 Distributed Systems' })).toBeVisible();

  // STEP 3: Upload PDF
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: 'raft-consensus-lecture.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4 sample'),
  });
  await expect(page.getByText('raft-consensus-lecture.pdf').first()).toBeVisible();

  // STEP 4: Select concept (on Course Overview tab)
  await page.goto(`/#/courses/${DEMO_COURSE_ID}`);
  const conceptSelect = page.getByLabel('1. Select Course Concept');
  await expect(conceptSelect).toBeVisible();
  await conceptSelect.selectOption(DEMO_CONCEPT_ID);

  // STEP 5: Start study session
  await page.getByRole('button', { name: 'Start Session' }).click();
  await expect(
    page.getByRole('heading', { name: 'Raft Leader Election & Quorum Safety' })
  ).toBeVisible();
  await expect(
    page.getByText('How do randomized election timeouts prevent indefinite split votes in Raft?')
  ).toBeVisible();

  // STEP 6: Answer question
  await page
    .getByLabel(/Your Reasoning & Answer/i)
    .fill(
      'Raft uses randomized election timeouts (150ms–300ms) so one follower times out first, requests votes, and wins a majority before split votes occur.'
    );
  await page.getByRole('button', { name: 'Submit Answer' }).click();

  // STEP 7: Receive assessment
  await expect(page.getByTestId('assessment-feedback-card')).toBeVisible();
  await expect(page.getByTestId('assessment-verdict-badge')).toContainText('Correct');
  await expect(page.getByTestId('learning-coach-recommendation-box')).toContainText(
    'Harder Practice'
  );

  // STEP 8: Receive adaptive activity
  await page.getByRole('button', { name: /Continue: Harder Practice/i }).click();
  await expect(
    page.getByText(/Suppose a network partition isolates the old Raft leader/i)
  ).toBeVisible();
  await expect(page.getByText('ADVANCED').first()).toBeVisible();

  // STEP 9: View updated learning profile
  await page.goto(`/#/courses/${DEMO_COURSE_ID}/profile`);
  await expect(page.getByTestId('learning-profile-view')).toBeVisible();
  await expect(page.getByTestId('learning-profile-view')).toContainText('76/100');
  await expect(page.getByTestId('learning-profile-strengths')).toContainText(
    'Clear explanation of randomized election timeouts and majority votes'
  );

  // STEP 10: Reopen session
  await page.goto(`/#/courses/${DEMO_COURSE_ID}/sessions`);
  await expect(page.getByTestId('session-history')).toContainText(
    'Raft Leader Election & Quorum Safety'
  );
  await page.getByRole('link', { name: 'Resume' }).click();
  await expect(
    page.getByText(/Suppose a network partition isolates the old Raft leader/i)
  ).toBeVisible();
  await expect(page.getByText('Session Activity History (1)')).toBeVisible();
});
