import { expect, test } from '@playwright/test';

const USER = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'student@university.edu',
  full_name: 'Ada Lovelace',
  is_active: true,
  created_at: '2026-11-04T10:00:00Z',
  updated_at: '2026-11-04T10:00:00Z',
};

const COURSE = {
  id: '22222222-2222-2222-2222-222222222222',
  user_id: USER.id,
  title: 'Distributed Systems',
  code: 'CS-401',
  description: 'Consensus, replication, and fault tolerance.',
  document_count: 1,
  created_at: '2026-11-04T10:00:00Z',
  updated_at: '2026-11-04T10:00:00Z',
};

const DOC = {
  id: '33333333-3333-3333-3333-333333333333',
  user_id: USER.id,
  course_id: COURSE.id,
  filename: 'raft-consensus.pdf',
  file_path: 'storage/raft-consensus.pdf',
  file_size_bytes: 120400,
  mime_type: 'application/pdf',
  page_count: 18,
  chunk_count: 2,
  status: 'READY',
  error_message: null,
  extraction_warnings: [],
  created_at: '2026-11-04T10:00:00Z',
  updated_at: '2026-11-04T10:00:00Z',
};

const CHUNKS = [
  {
    id: 'c1',
    document_id: DOC.id,
    course_id: COURSE.id,
    chroma_vector_id: 'vec-1',
    chunk_index: 0,
    page_start: 1,
    page_end: 1,
    page_number: 1,
    section_title: '1. Introduction to Raft',
    chunk_text: 'Raft decomposes consensus into leader election, log replication, and safety.',
    char_count: 76,
    created_at: '2026-11-04T10:00:00Z',
  },
  {
    id: 'c2',
    document_id: DOC.id,
    course_id: COURSE.id,
    chroma_vector_id: 'vec-2',
    chunk_index: 1,
    page_start: 4,
    page_end: 5,
    page_number: 4,
    section_title: '2. Leader Election & Term Numbers',
    chunk_text: 'Raft uses randomized election timeouts to prevent split-vote livelocks across terms.',
    char_count: 84,
    created_at: '2026-11-04T10:00:00Z',
  },
];

const CONCEPT = {
  id: '44444444-4444-4444-4444-444444444444',
  course_id: COURSE.id,
  source_document_id: DOC.id,
  title: 'Raft Leader Election',
  summary: 'Term numbers, heartbeats, and randomized election timeouts.',
  difficulty: 'INTERMEDIATE',
  display_order: 1,
  source_pages: [4, 5],
  created_at: '2026-11-04T10:00:00Z',
  updated_at: '2026-11-04T10:00:00Z',
};

const COACH_REC = {
  recommended_activity: 'TARGETED_PRACTICE',
  target_concept_id: CONCEPT.id,
  target_concept_title: CONCEPT.title,
  difficulty: 'INTERMEDIATE',
  reason: 'Recent partial answer showed understanding of terms but missed randomized timeouts.',
  requires_student_confirmation: false,
  policy_rule_applied: 'PARTIAL_EVIDENCE_TARGETED_PRACTICE',
  evidence_status: 'PARTIAL_EVIDENCE',
  uncertainty_score: 0.25,
  alternative_activities: [
    {
      activity_type: 'EXPLANATION',
      label: 'Read guided explanation',
      difficulty: 'BASIC',
      description: 'Review how randomized timeouts prevent split votes.',
    },
  ],
};

const SESSION_ID = '55555555-5555-5555-5555-555555555555';

const BASE_ACTIVITY = {
  id: '66666666-6666-6666-6666-666666666666',
  session_id: SESSION_ID,
  concept_id: CONCEPT.id,
  activity_type: 'DIAGNOSTIC_QUESTION',
  difficulty: 'INTERMEDIATE',
  prompt_text: 'How does Raft prevent indefinite split votes during leader election?',
  status: 'ACTIVE',
  order_index: 1,
  relevant_pages: [4, 5],
  source_excerpts: [
    {
      document_id: DOC.id,
      filename: DOC.filename,
      page_start: 4,
      page_end: 5,
      section_title: '2. Leader Election & Term Numbers',
      excerpt: 'Raft uses randomized election timeouts to prevent split-vote livelocks across terms.',
    },
  ],
  hints_used: [] as string[],
  total_hints_available: 3,
  explanation_requested: null as string | null,
  attempts: [] as unknown[],
  created_at: '2026-11-04T10:05:00Z',
};

test('Phase 8 end-to-end journey across all 12 screens, responsive layout, and auth expiry', async ({
  page,
}) => {
  const courses = [COURSE];
  const documents = [DOC];
  let revisionStatus: 'PENDING' | 'COMPLETED' | 'DISMISSED' = 'PENDING';
  let currentSession: Record<string, unknown> = {
    id: SESSION_ID,
    user_id: USER.id,
    course_id: COURSE.id,
    course_title: COURSE.title,
    current_concept_id: CONCEPT.id,
    concept_title: CONCEPT.title,
    concept_summary: CONCEPT.summary,
    learning_goal: 'Master Raft Leader Election',
    state: 'ACTIVE',
    started_at: '2026-11-04T10:05:00Z',
    updated_at: '2026-11-04T10:05:00Z',
    completed_at: null,
    current_activity: { ...BASE_ACTIVITY },
    activity_history: [{ ...BASE_ACTIVITY }],
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
    coach_recommendation: COACH_REC,
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
          access_token: 'valid-token-123',
          token_type: 'bearer',
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          user: USER,
        }),
      });
    }

    if (path === '/api/v1/auth/login' && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'valid-token-456',
          token_type: 'bearer',
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          user: USER,
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
        ...COURSE,
        id: '77777777-7777-7777-7777-777777777777',
        title: body.title,
        code: body.code || null,
        description: body.description || null,
      };
      courses.push(created);
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(created),
      });
    }

    if (path.startsWith('/api/v1/courses/') && method === 'GET' && path.split('/').length === 5) {
      const cid = path.split('/')[4];
      const found = courses.find((c) => c.id === cid) ?? COURSE;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...found, document_count: documents.length }),
      });
    }

    if (path.endsWith('/documents') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(documents),
      });
    }

    if (path.endsWith('/documents') && method === 'POST') {
      const uploaded = {
        ...DOC,
        id: '88888888-8888-8888-8888-888888888888',
        filename: 'paxos-made-simple.pdf',
      };
      documents.push(uploaded);
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(uploaded),
      });
    }

    if (path === `/api/v1/documents/${DOC.id}` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(DOC),
      });
    }

    if (path === `/api/v1/documents/${DOC.id}/chunks` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(CHUNKS),
      });
    }

    if (path === `/api/v1/documents/${DOC.id}/file` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/pdf',
        body: Buffer.from('%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'),
      });
    }

    if (path.endsWith('/concepts') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([CONCEPT]),
      });
    }

    if (path.endsWith('/learning-profile') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: USER.id,
          course_id: COURSE.id,
          course_title: COURSE.title,
          total_concepts: 1,
          mastered_concepts_count: 0,
          learning_concepts_count: 1,
          needs_review_concepts_count: 0,
          not_started_concepts_count: 0,
          overall_mastery_score: 55,
          overall_uncertainty_score: 0.25,
          observed_strengths: ['Understands monotonic term numbers'],
          areas_needing_practice: ['Randomized election timeout interval reasoning'],
          recommended_next_action: COACH_REC,
          concepts: [
            {
              concept_id: CONCEPT.id,
              course_id: COURSE.id,
              title: CONCEPT.title,
              summary: CONCEPT.summary,
              display_order: 1,
              source_pages: [4, 5],
              prerequisite_concept_ids: [],
              mastery_score: 55,
              mastery_status: 'LEARNING',
              evidence_status: 'PARTIAL_EVIDENCE',
              uncertainty_score: 0.25,
              attempts_count: 2,
              correct_attempts_count: 1,
              independent_success_count: 0,
              assisted_success_count: 1,
              last_score: 65,
              last_practiced_at: '2026-11-04T10:10:00Z',
              next_review_at: '2026-11-05T10:10:00Z',
              observed_strengths: ['Understands monotonic term numbers'],
              areas_needing_practice: ['Randomized election timeout interval reasoning'],
              recent_evidence: [
                {
                  id: 'ev-1',
                  user_id: USER.id,
                  concept_id: CONCEPT.id,
                  evaluation_id: 'eval-1',
                  evidence_type: 'ASSESSMENT',
                  score_delta: 0.15,
                  observed_score: 65,
                  summary: 'Partial explanation of Raft election safety.',
                  metadata_json: {},
                  created_at: '2026-11-04T10:10:00Z',
                },
              ],
              recommended_next_action: COACH_REC,
            },
          ],
          concept_map: [],
          recent_activity: [
            {
              evidence_id: 'ev-1',
              concept_id: CONCEPT.id,
              concept_title: CONCEPT.title,
              evidence_type: 'ASSESSMENT',
              observed_score: 65,
              score_delta: 0.15,
              verdict: 'PARTIALLY_CORRECT',
              hints_used: 1,
              difficulty: 'INTERMEDIATE',
              summary: 'Explained term numbers accurately.',
              created_at: '2026-11-04T10:10:00Z',
            },
          ],
          revision_recommendations: [
            {
              id: 'rev-1',
              course_id: COURSE.id,
              concept_id: CONCEPT.id,
              concept_title: CONCEPT.title,
              title: 'Practice randomized election timeouts in Raft',
              reason: 'Partial evidence recorded on last diagnostic question.',
              priority: 'HIGH',
              status: revisionStatus,
              recommended_activity: 'TARGETED_PRACTICE',
              due_at: '2026-11-05T10:00:00Z',
              completed_at: null,
              created_at: '2026-11-04T10:10:00Z',
            },
          ],
        }),
      });
    }

    if (path === '/api/v1/revision-tasks/rev-1' && method === 'PATCH') {
      const body = JSON.parse(req.postData() || '{}');
      revisionStatus = body.status;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'rev-1',
          course_id: COURSE.id,
          concept_id: CONCEPT.id,
          concept_title: CONCEPT.title,
          title: 'Practice randomized election timeouts in Raft',
          reason: 'Partial evidence recorded on last diagnostic question.',
          priority: 'HIGH',
          status: revisionStatus,
          recommended_activity: 'TARGETED_PRACTICE',
          due_at: '2026-11-05T10:00:00Z',
          completed_at: '2026-11-04T10:20:00Z',
          created_at: '2026-11-04T10:10:00Z',
        }),
      });
    }

    if (path.endsWith('/ask') && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer:
            'Raft prevents split votes by assigning each candidate a randomized election timeout between 150ms and 300ms [Source 1, p. 4].',
          comprehension_questions: [
            'What happens if two followers still time out at the exact same millisecond?',
          ],
          hints: ['Consider how the next term increments when no majority is reached.'],
          source_references: [
            {
              source_index: 1,
              document_id: DOC.id,
              filename: DOC.filename,
              chunk_index: 1,
              page_start: 4,
              page_end: 5,
              section_title: '2. Leader Election & Term Numbers',
              excerpt:
                'Raft uses randomized election timeouts to prevent split-vote livelocks across terms.',
              relevance_score: 0.94,
            },
          ],
          relevant_pages: [4, 5],
          relevant_page_numbers: [4, 5],
          retrieval_metadata: {
            top_k_requested: 4,
            passages_retrieved: 1,
            total_candidates_indexed: 2,
            retrieval_latency_ms: 12,
            embedding_model: 'all-MiniLM-L6-v2',
            llm_model: 'llama3.2',
            max_relevance_score: 0.94,
          },
          insufficient_evidence: false,
        }),
      });
    }

    if (path.endsWith('/sessions') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([currentSession]),
      });
    }

    if (path === '/api/v1/sessions' && method === 'POST') {
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(currentSession),
      });
    }

    if (path === `/api/v1/sessions/${SESSION_ID}` && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(currentSession),
      });
    }

    if (path === `/api/v1/sessions/${SESSION_ID}/hint` && method === 'POST') {
      const updatedAct = {
        ...(currentSession.current_activity as typeof BASE_ACTIVITY),
        hints_used: [
          'Think about whether all followers wait the exact same duration before starting an election.',
        ],
      };
      currentSession = {
        ...currentSession,
        current_activity: updatedAct,
        activity_history: [updatedAct],
      };
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session_id: SESSION_ID,
          activity_id: BASE_ACTIVITY.id,
          hint_level: 1,
          max_hints: 3,
          hint_text:
            'Think about whether all followers wait the exact same duration before starting an election.',
          relevant_pages: [4, 5],
        }),
      });
    }

    if (path === `/api/v1/sessions/${SESSION_ID}/submit-answer` && method === 'POST') {
      const attempt = {
        id: 'att-1',
        activity_id: BASE_ACTIVITY.id,
        user_id: USER.id,
        attempt_number: 1,
        response_text:
          'Raft uses randomized election timeouts so one candidate requests votes before others time out.',
        time_spent_seconds: 25,
        submitted_at: '2026-11-04T10:12:00Z',
        created_at: '2026-11-04T10:12:00Z',
      };
      const evaluation = {
        id: 'eval-1',
        attempt_id: 'att-1',
        concept_id: CONCEPT.id,
        verdict: 'CORRECT',
        rubric_score: 0.92,
        total_score: 92,
        max_score: 100,
        passed: true,
        criteria_scores_json: [
          {
            criterion_id: 'c1',
            name: 'Randomized Election Timeout',
            awarded_points: 50,
            max_points: 50,
            matched_ideas: ['randomized election timeouts'],
            missing_ideas: [],
            feedback: 'Accurately identified randomized timeouts.',
          },
        ],
        strengths_json: ['Clearly explained how randomized timeouts break symmetry'],
        strengths: ['Clearly explained how randomized timeouts break symmetry'],
        gaps_json: [],
        gaps: [],
        misconception: null,
        evidence_json: ['randomized election timeouts'],
        evidence: ['randomized election timeouts'],
        confidence: 0.93,
        next_activity: 'HARDER_PRACTICE',
        error_classification: 'NONE',
        uncertain_evaluation: false,
        prompt_version: 'v1',
        overall_feedback:
          'Strong explanation! Randomized timeouts ensure one follower typically times out first and wins the majority.',
        evaluator_model: 'deterministic+llm',
        coach_action: 'ADVANCE',
        evaluated_at: '2026-11-04T10:12:00Z',
        created_at: '2026-11-04T10:12:00Z',
      };
      const updatedAct = {
        ...(currentSession.current_activity as typeof BASE_ACTIVITY),
        status: 'COMPLETED',
        attempts: [{ attempt, evaluation }],
      };
      currentSession = {
        ...currentSession,
        state: 'FEEDBACK_READY',
        current_activity: updatedAct,
        activity_history: [updatedAct],
        progress: {
          total_activities_generated: 1,
          completed_activities_count: 1,
          current_activity_index: 1,
          total_attempts_submitted: 1,
          hints_used_count: 1,
          explanations_requested_count: 0,
          current_difficulty: 'INTERMEDIATE',
          average_score: 92,
        },
      };
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session: currentSession,
          attempt,
          evaluation,
          coach_recommendation: COACH_REC,
          duplicate_prevented: false,
        }),
      });
    }

    if (path === `/api/v1/sessions/${SESSION_ID}/end` && method === 'POST') {
      currentSession = {
        ...currentSession,
        state: 'COMPLETED',
        completed_at: '2026-11-04T10:15:00Z',
        current_activity: null,
        summary: {
          total_activities: 1,
          completed_activities: 1,
          total_attempts: 1,
          hints_used_count: 1,
          explanations_requested_count: 0,
          average_score: 92,
          concept_title: CONCEPT.title,
          learning_goal: 'Master Raft Leader Election',
          pages_reviewed: [4, 5],
          strengths: ['Clearly explained how randomized timeouts break symmetry'],
          areas_for_improvement: [],
          key_takeaways: ['Randomized election timeouts prevent split votes in Raft.'],
          recommended_next_steps: 'Proceed to Log Replication.',
        },
      };
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(currentSession),
      });
    }

    return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  // 1. Unauthenticated access redirects to Login (#/login), then switch to Registration (#/register)
  await page.goto('/#/');
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await page.getByRole('link', { name: 'Create an account' }).click();
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();

  // 2. Register account -> lands on Dashboard (#/)
  await page.getByLabel('Full name').fill('Ada Lovelace');
  await page.getByLabel('University email').fill('student@university.edu');
  await page.getByLabel('Password', { exact: true }).fill('securePass123');
  await page.getByLabel('Confirm password').fill('securePass123');
  await page.getByRole('button', { name: 'Create account' }).click();

  // 3. Dashboard displays all 5 required sections + dark mode toggle
  await expect(page.getByRole('heading', { name: /Welcome back, Ada/i })).toBeVisible();
  await expect(page.getByTestId('suggested-activity')).toContainText('Raft Leader Election');
  await expect(page.getByText('Distributed Systems').first()).toBeVisible();
  await expect(page.getByTestId('practice-list')).toContainText('Raft Leader Election');
  await expect(page.getByTestId('recent-concepts')).toContainText('Raft Leader Election');
  await expect(page.getByTestId('recent-sessions')).toContainText('Raft Leader Election');

  // Toggle Dark Mode & verify `dark` class on <html>
  await page.getByRole('button', { name: /Switch to dark mode/i }).click();
  await expect(page.locator('html')).toHaveClass(/dark/);

  // 4. Create a new Course on the Dashboard
  await page.getByRole('button', { name: 'New course' }).click();
  await page.getByLabel(/Course Title/i).fill('Operating Systems');
  await page.getByRole('button', { name: /Create Course/i }).click();
  await expect(page.getByRole('heading', { name: 'Operating Systems' })).toBeVisible();

  // 5. Open Course Workspace (#/courses/:courseId) & Document Management (#/courses/:courseId/documents)
  await page.goto(`/#/courses/${COURSE.id}/documents`);
  await expect(page.getByRole('heading', { name: 'Distributed Systems' })).toBeVisible();
  await expect(page.getByText('raft-consensus.pdf')).toBeVisible();

  // 6. Open PDF Viewer / Source Preview (#/courses/:courseId/documents/:docId?page=4)
  await page.goto(`/#/courses/${COURSE.id}/documents/${DOC.id}?page=4`);
  await expect(page.getByRole('heading', { name: 'raft-consensus.pdf' })).toBeVisible();
  await expect(page.getByTestId('source-preview')).toContainText(
    'Raft uses randomized election timeouts'
  );

  // 7. AI Tutor (#/courses/:courseId/tutor) with grounded citation
  await page.goto(`/#/courses/${COURSE.id}/tutor`);
  await page
    .getByPlaceholder(/Ask a question about your uploaded course materials/i)
    .fill('How does Raft prevent split votes during leader election?');
  await page.getByRole('button', { name: 'Ask Tutor' }).click();
  await expect(page.getByText(/randomized election timeout between 150ms and 300ms/i)).toBeVisible();

  // 8. Learning Profile (#/courses/:courseId/profile)
  await page.goto(`/#/courses/${COURSE.id}/profile`);
  await expect(page.getByTestId('learning-profile-view')).toBeVisible();
  await expect(page.getByTestId('learning-profile-view')).toContainText('Raft Leader Election');
  await expect(page.getByTestId('learning-profile-strengths')).toContainText(
    'Understands monotonic term numbers'
  );

  // 9. Session History (#/courses/:courseId/sessions)
  await page.goto(`/#/courses/${COURSE.id}/sessions`);
  await expect(page.getByTestId('session-history')).toBeVisible();
  await expect(page.getByTestId('session-history')).toContainText('Raft Leader Election');

  // 10. Revision Recommendations (#/courses/:courseId/revision)
  await page.goto(`/#/courses/${COURSE.id}/revision`);
  await expect(page.getByTestId('revision-recommendations-view')).toBeVisible();
  await expect(page.getByTestId('revision-recommendations-view')).toContainText(
    'Practice randomized election timeouts in Raft'
  );
  await page.getByRole('button', { name: 'Mark complete' }).click();
  await expect(page.getByTestId('revision-recommendations-view')).toContainText('completed');

  // 11. Study Session (#/courses/:courseId/sessions/:sessionId) + Hints + Assessment Feedback + Summary
  await page.goto(`/#/courses/${COURSE.id}/sessions/${SESSION_ID}`);
  await expect(page.getByRole('heading', { name: 'Raft Leader Election' })).toBeVisible();
  await expect(page.getByTestId('session-sources')).toContainText('raft-consensus.pdf');

  // Request a graduated hint
  await page.getByRole('button', { name: /Get Graduated Hint/i }).click();
  await expect(
    page.getByText('Think about whether all followers wait the exact same duration')
  ).toBeVisible();

  // Submit answer & verify Assessment Feedback card (12th view)
  await page
    .getByLabel(/Your Reasoning & Answer/i)
    .fill(
      'Raft uses randomized election timeouts so one candidate requests votes before others time out.'
    );
  await page.getByRole('button', { name: 'Submit Answer' }).click();
  await expect(page.getByTestId('assessment-feedback-card')).toBeVisible();
  await expect(page.getByTestId('assessment-verdict-badge')).toContainText('Correct');

  // End session & verify Session Summary view
  await page.getByRole('button', { name: /End Session & View Summary/i }).first().click();
  await expect(page.getByText(/Learning Session Summary: Raft Leader Election/i)).toBeVisible();
  await expect(page.getByText('92 / 100').first()).toBeVisible();

  // 12. Responsive mobile drawer test
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByLabel('Toggle navigation menu').click();
  await expect(page.getByLabel('Toggle navigation menu')).toHaveAttribute('aria-expanded', 'true');

  // 13. Expired authentication handling (`401 TOKEN_EXPIRED`) auto-logs out and shows notice on #/login
  await page.route('**/api/v1/courses/**', async (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({
        error_code: 'TOKEN_EXPIRED',
        detail: 'Your session has expired. Please sign in again.',
      }),
    })
  );
  await page.goto(`/#/courses/99999999-9999-9999-9999-999999999999`);
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
  await expect(page.getByText(/expired/i)).toBeVisible();
});
