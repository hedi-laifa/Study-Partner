import React, { useEffect } from 'react';
import { AppShell, type NavId } from '../components/layout/AppShell';
import { LoadingState, EmptyState } from '../components/ui/States';
import { LoginPage, RegisterPage, useAuth } from '../features/auth';
import { useTheme } from '../hooks/useTheme';
import {
  CourseWorkspacePage,
  isCourseTab,
} from '../pages/CourseWorkspacePage';
import { DashboardPage } from '../pages/DashboardPage';
import { DocumentViewerPage } from '../pages/DocumentViewerPage';
import { StudySessionRoutePage } from '../pages/StudySessionRoutePage';
import { SystemHealthPage } from '../pages/SystemHealthPage';
import { Link, matchPath, navigate, useRoute } from './router';

const PUBLIC_PATHS = ['/login', '/register', '/system'];

export const App: React.FC = () => {
  const { status, user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { path, search } = useRoute();

  const isPublic = PUBLIC_PATHS.includes(path);

  // Auth gating (effects, so navigation never happens during render)
  useEffect(() => {
    if (status === 'anonymous' && !isPublic) navigate('/login', { replace: true });
    if (status === 'authenticated' && (path === '/login' || path === '/register')) {
      navigate('/', { replace: true });
    }
  }, [status, isPublic, path]);

  let activeNav: NavId | null = null;
  let content: React.ReactNode;

  if (status === 'loading') {
    content = <LoadingState label="Restoring your session…" />;
  } else if (path === '/system') {
    activeNav = 'system';
    content = <SystemHealthPage />;
  } else if (status === 'anonymous') {
    content =
      path === '/register' ? (
        <RegisterPage />
      ) : path === '/login' ? (
        <LoginPage />
      ) : (
        <LoadingState label="Redirecting to sign in…" />
      );
  } else if (user) {
    const userId = user.id;
    const viewer = matchPath('/courses/:courseId/documents/:docId', path);
    const sessionRoute = matchPath('/courses/:courseId/sessions/:sessionId', path);
    const course = matchPath('/courses/:courseId/:tab?', path);

    if (path === '/') {
      activeNav = 'dashboard';
      content = <DashboardPage userId={userId} userName={user.full_name} />;
    } else if (viewer) {
      const rawPage = Number.parseInt(search.get('page') ?? '', 10);
      content = (
        <DocumentViewerPage
          key={`${viewer.docId}`}
          courseId={viewer.courseId}
          documentId={viewer.docId}
          userId={userId}
          page={Number.isFinite(rawPage) && rawPage > 0 ? rawPage : null}
        />
      );
    } else if (sessionRoute) {
      content = (
        <StudySessionRoutePage
          key={sessionRoute.sessionId}
          courseId={sessionRoute.courseId}
          sessionId={sessionRoute.sessionId}
          userId={userId}
        />
      );
    } else if (course && (course.tab === undefined || isCourseTab(course.tab))) {
      content = (
        <CourseWorkspacePage
          key={course.courseId}
          courseId={course.courseId}
          tab={isCourseTab(course.tab) ? course.tab : 'overview'}
          userId={userId}
        />
      );
    } else {
      content = (
        <EmptyState
          title="Page not found"
          description="The page you are looking for does not exist."
          action={
            <Link
              to="/"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              Go to dashboard
            </Link>
          }
        />
      );
    }
  } else {
    content = <LoadingState />;
  }

  return (
    <AppShell
      user={user}
      activeNav={activeNav}
      theme={theme}
      onToggleTheme={toggleTheme}
      onLogout={() => {
        logout();
        navigate('/login', { replace: true });
      }}
    >
      {content}
    </AppShell>
  );
};

export default App;
