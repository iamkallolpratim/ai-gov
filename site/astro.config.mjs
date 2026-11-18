// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import starlightOpenAPI, { openAPISidebarGroups } from 'starlight-openapi';
import regoGrammar from './src/lib/rego.tmLanguage.json' with { type: 'json' };

// Served from GitHub Pages at https://iamkallolpratim.github.io/ai-gov/.
// For a custom domain: add public/CNAME, set SITE_URL to the domain and SITE_BASE to "/".
const site = process.env.SITE_URL ?? 'https://iamkallolpratim.github.io';
const base = process.env.SITE_BASE ?? '/ai-gov';

// Privacy-friendly, cookieless analytics. Only emitted when a code is configured, so
// forks and local builds never report to the upstream account.
const goatcounter = process.env.PUBLIC_GOATCOUNTER_CODE;

const repo = 'https://github.com/iamkallolpratim/ai-gov';

export default defineConfig({
  site,
  base,
  trailingSlash: 'always',
  integrations: [
    starlight({
      title: 'AI Governance Console',
      description:
        'Open-source AI compliance as code: inventory, jurisdiction detection, risk classification, OPA policy checks and evidence packages.',
      logo: { src: './src/assets/logo.svg', replacesTitle: false },
      favicon: '/favicon.svg',
      social: [{ icon: 'github', label: 'GitHub', href: repo }],
      editLink: { baseUrl: `${repo}/edit/production/site/` },
      lastUpdated: true,
      customCss: ['./src/styles/starlight.css'],
      // Shiki ships no Rego grammar; a small TextMate grammar covers the docs' snippets.
      expressiveCode: { shiki: { langs: [/** @type {any} */ (regoGrammar)] } },
      head: [
        { tag: 'meta', attrs: { property: 'og:image', content: `${site}${base}/og.png` } },
        { tag: 'meta', attrs: { name: 'twitter:card', content: 'summary_large_image' } },
        ...(goatcounter
          ? [
              {
                tag: /** @type {const} */ ('script'),
                attrs: {
                  async: true,
                  src: 'https://gc.zgo.at/count.js',
                  'data-goatcounter': `https://${goatcounter}.goatcounter.com/count`,
                },
              },
            ]
          : []),
      ],
      plugins: [
        starlightOpenAPI([
          {
            base: 'docs/api',
            schema: './openapi.json',
            sidebar: { label: 'API reference', collapsed: true },
          },
        ]),
      ],
      sidebar: [
        {
          label: 'Start here',
          items: [
            { label: 'Introduction', slug: 'docs' },
            { label: 'Quickstart', slug: 'docs/quickstart' },
            { label: 'Self-hosting', slug: 'docs/self-hosting' },
          ],
        },
        {
          label: 'Concepts',
          items: [
            { label: 'How it works', slug: 'docs/concepts/how-it-works' },
            { label: 'Jurisdiction detection', slug: 'docs/concepts/jurisdiction-detection' },
            { label: 'Risk classification', slug: 'docs/concepts/risk-classification' },
            { label: 'Evidence & audit trail', slug: 'docs/concepts/evidence-and-audit' },
          ],
        },
        {
          label: 'Policies',
          items: [{ label: 'Writing Rego policies', slug: 'docs/policies/writing-rego' }],
        },
        {
          label: 'Regulations',
          items: [
            { label: 'EU AI Act', slug: 'docs/regulations/eu-ai-act' },
            { label: 'California ADMT', slug: 'docs/regulations/california-admt' },
            { label: 'China generative AI', slug: 'docs/regulations/china-genai' },
            { label: 'India DPDP', slug: 'docs/regulations/india-dpdp' },
          ],
        },
        ...openAPISidebarGroups,
        {
          label: 'Project',
          items: [
            { label: 'Contributing', slug: 'docs/contributing' },
            { label: 'FAQ', slug: 'docs/faq' },
          ],
        },
      ],
    }),
  ],
});
