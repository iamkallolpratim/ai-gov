/**
 * Jurisdiction facts shown on the landing page. Mirrors JURISDICTIONS in
 * app/db/seed.py and the shipped rules in app/services/jurisdiction_engine.py;
 * keep the two in step. Rule counts are NOT stored here: they come from
 * policies/ at build time (see policy-stats.ts).
 */
export interface JurisdictionCard {
  code: string;
  name: string;
  regulation: string;
  /** Directory under policies/ holding this regime's Rego. */
  policyDir: string;
  strictness: number;
  tiers: string[];
  triggers: string[];
  docs: string;
}

export const JURISDICTIONS: JurisdictionCard[] = [
  {
    code: 'EU',
    name: 'European Union',
    regulation: 'EU AI Act — Regulation (EU) 2024/1689',
    policyDir: 'eu',
    strictness: 100,
    tiers: ['Prohibited (Art. 5)', 'High-risk (Annex III)', 'Limited (Art. 50)', 'Minimal'],
    triggers: ['Deployed, offered or with data subjects in the EU/EEA', 'Automated consequential decisions about EU residents'],
    docs: 'docs/regulations/eu-ai-act/',
  },
  {
    code: 'CN',
    name: 'China',
    regulation: 'Generative AI Interim Measures · PIPL · algorithm filing',
    policyDir: 'cn',
    strictness: 90,
    tiers: ['Prohibited service', 'Public-opinion attributes', 'Filing-only', 'Minimal'],
    triggers: ['Service reachable from China', 'Generated content viewable in China', 'Data stored or processed in China'],
    docs: 'docs/regulations/china-genai/',
  },
  {
    code: 'CA',
    name: 'California',
    regulation: 'CCPA/CPRA ADMT regulations · AI Transparency Act',
    policyDir: 'ca',
    strictness: 70,
    tiers: ['Significant-decision ADMT', 'Disclosure-required', 'Minimal'],
    triggers: ['Deployed or offered in California', 'Automated decisions on employment, credit, housing, insurance, education'],
    docs: 'docs/regulations/california-admt/',
  },
  {
    code: 'IN',
    name: 'India',
    regulation: 'Digital Personal Data Protection Act 2023',
    policyDir: 'in',
    strictness: 60,
    tiers: ['Significant data fiduciary workload', 'Standard workload', 'Minimal'],
    triggers: ['Users, data subjects or deployment in India', "Children's data escalates the tier"],
    docs: 'docs/regulations/india-dpdp/',
  },
];
