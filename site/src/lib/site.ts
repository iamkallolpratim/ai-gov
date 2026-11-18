export const REPO_URL = 'https://github.com/iamkallolpratim/ai-gov';

/** Live demo URL. Empty until the hosted demo exists (Phase 4); the button hides itself. */
export const DEMO_URL = import.meta.env.PUBLIC_DEMO_URL ?? '';

/** Join a path onto the configured base ("/ai-gov/"), tolerating either slash style. */
export function href(path = ''): string {
  const base = import.meta.env.BASE_URL.replace(/\/+$/, '');
  const clean = path.replace(/^\/+/, '');
  return clean ? `${base}/${clean}` : `${base}/`;
}
