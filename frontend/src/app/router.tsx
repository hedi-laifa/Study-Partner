/* eslint-disable react-refresh/only-export-components */
import React, { useEffect, useState } from 'react';

/** Minimal dependency-free hash router (`#/path?query`). */

function readLocation(): { path: string; search: URLSearchParams } {
  const raw = window.location.hash.replace(/^#/, '') || '/';
  const [path, query = ''] = raw.split('?');
  return { path: path || '/', search: new URLSearchParams(query) };
}

export function navigate(to: string, options?: { replace?: boolean }): void {
  const target = `#${to.startsWith('/') ? to : `/${to}`}`;
  if (options?.replace) {
    window.location.replace(target);
  } else {
    window.location.hash = target;
  }
}

export function useRoute(): { path: string; search: URLSearchParams } {
  const [route, setRoute] = useState(readLocation);
  useEffect(() => {
    const onChange = () => setRoute(readLocation());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return route;
}

/** Match `/courses/:id/:tab?` style patterns. Returns params or null. */
export function matchPath(
  pattern: string,
  path: string
): Record<string, string> | null {
  const patternParts = pattern.split('/').filter(Boolean);
  const pathParts = path.split('/').filter(Boolean);
  const params: Record<string, string> = {};
  for (let i = 0; i < patternParts.length; i += 1) {
    const part = patternParts[i];
    const optional = part.endsWith('?');
    const name = part.replace(/[:?]/g, '');
    const value = pathParts[i];
    if (part.startsWith(':')) {
      if (value === undefined) {
        if (optional) continue;
        return null;
      }
      params[name] = decodeURIComponent(value);
    } else if (value !== part) {
      return null;
    }
  }
  return pathParts.length > patternParts.length ? null : params;
}

interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  to: string;
}

export const Link: React.FC<LinkProps> = ({ to, children, ...rest }) => (
  <a href={`#${to}`} {...rest}>
    {children}
  </a>
);
