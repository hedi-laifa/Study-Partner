import React from 'react';
import { StatusBadge } from '../components/ui/StatusBadge';
import { useBackendHealth } from '../hooks/useBackendHealth';
import { API_BASE_URL, formatIsoTimestamp } from '../utils/config';

export const SystemHealthPage: React.FC = () => {
  const { data, isLoading, error, refresh } = useBackendHealth();

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-line bg-surface p-6 shadow-warm-sm sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="font-display text-2xl font-bold tracking-tight text-ink">
              System Foundation &amp; Health Check
            </h2>
            <p className="mt-1 text-sm text-ink/70">
              Verifies independent operation of the React frontend and connectivity to the FastAPI backend.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={isLoading}
            className="rounded-xl bg-forest px-4 py-2 text-sm font-semibold text-paper shadow-warm-sm transition-all hover:bg-forest/90 disabled:opacity-50"
          >
            {isLoading ? 'Checking...' : 'Refresh Status'}
          </button>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {/* Frontend Health Card */}
          <div className="rounded-xl border border-line bg-paper/50 p-5 shadow-warm-sm">
            <div className="flex items-center justify-between">
              <span className="font-display text-sm font-bold text-ink">
                Frontend Application (React + Vite)
              </span>
              <StatusBadge label="Operational" variant="healthy" />
            </div>
            <dl className="mt-3 space-y-1.5 text-xs text-ink/70">
              <div className="flex justify-between">
                <dt>Status:</dt>
                <dd className="font-semibold text-forest">Ready</dd>
              </div>
              <div className="flex justify-between">
                <dt>Configured API URL:</dt>
                <dd className="font-mono text-ink">{API_BASE_URL}</dd>
              </div>
            </dl>
          </div>

          {/* Backend Health Card */}
          <div className="rounded-xl border border-line bg-paper/50 p-5 shadow-warm-sm">
            <div className="flex items-center justify-between">
              <span className="font-display text-sm font-bold text-ink">
                Backend API (FastAPI)
              </span>
              {isLoading ? (
                <StatusBadge label="Checking..." variant="warning" />
              ) : data?.status === 'ok' ? (
                <StatusBadge label="Connected" variant="healthy" />
              ) : (
                <StatusBadge label="Standalone / Offline" variant="offline" />
              )}
            </div>

            {data ? (
              <dl className="mt-3 space-y-1.5 text-xs text-ink/70">
                <div className="flex justify-between">
                  <dt>Service:</dt>
                  <dd className="font-medium text-ink">{data.service}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Version / Env:</dt>
                  <dd className="font-mono text-ink">
                    v{data.version} ({data.environment})
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt>Timestamp:</dt>
                  <dd className="text-ink">
                    {formatIsoTimestamp(data.timestamp)}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="mt-3 text-xs text-ink/70">
                {error
                  ? `Backend not reachable (${error}). The frontend runs independently; start the FastAPI server on port 8000 to connect.`
                  : 'Probing backend health endpoint...'}
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-line bg-surface p-6 shadow-warm-sm">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/60">
          Initialized Feature Modules
        </h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[
            { name: 'auth', desc: 'Student profile & workspace context' },
            { name: 'courses', desc: 'Course & PDF document management' },
            { name: 'study-session', desc: 'Tutor Agent guided explanations' },
            { name: 'assessment', desc: 'Questions & rubric evaluation' },
            { name: 'learning-progress', desc: 'Mastery tracking & coaching' },
          ].map((mod) => (
            <div
              key={mod.name}
              className="rounded-xl border border-line bg-paper/40 p-3.5 text-xs shadow-warm-sm transition-all hover:border-forest/30"
            >
              <div className="font-mono font-bold text-forest">
                features/{mod.name}
              </div>
              <p className="mt-1 text-ink/70">{mod.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
