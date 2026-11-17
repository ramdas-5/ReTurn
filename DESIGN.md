# Web Experiences, Apps & Automation

## Mission
Create implementation-ready, token-driven UI guidance for Web Experiences, Apps & Automation that is optimized for consistency, accessibility, and fast delivery across e-commerce storefront.

## Brand
- Product/brand: Web Experiences, Apps & Automation
- URL: https://kigo.studio/
- Audience: online shoppers and consumers
- Product surface: e-commerce storefront

## Style Foundations
- Visual style: clean, functional, implementation-oriented
- Main font style: `font.family.primary=Poppins`, `font.family.stack=Poppins, Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Oxygen, Ubuntu, Cantarell, Fira Sans, Droid Sans, Helvetica Neue, sans-serif`, `font.size.base=20px`, `font.weight.base=400`, `font.lineHeight.base=20px`
- Typography scale: `font.size.xs=13px`, `font.size.sm=13.33px`, `font.size.md=14px`, `font.size.lg=15px`, `font.size.xl=17px`, `font.size.2xl=18px`, `font.size.3xl=20px`, `font.size.4xl=22.5px`
- Color palette: `color.text.primary=#202020`, `color.text.secondary=#242723`, `color.text.tertiary=#4a4144`, `color.text.inverse=#7c1d25`, `color.surface.base=#000000`, `color.surface.muted=#ffffff`
- Spacing scale: `space.1=5px`, `space.2=6px`, `space.3=12px`, `space.4=14px`, `space.5=16px`, `space.6=17px`, `space.7=18px`, `space.8=20px`
- Radius/shadow/motion tokens: `motion.duration.instant=300ms`, `motion.duration.fast=500ms`, `motion.duration.normal=800ms`

## Accessibility
- Target: WCAG 2.2 AA
- Keyboard-first interactions required.
- Focus-visible rules required.
- Contrast constraints required.

## Writing Tone
Concise, confident, implementation-focused.

## Rules: Do
- Use semantic tokens, not raw hex values, in component guidance.
- Every component must define states for default, hover, focus-visible, active, disabled, loading, and error.
- Component behavior should specify responsive and edge-case handling.
- Interactive components must document keyboard, pointer, and touch behavior.
- Accessibility acceptance criteria must be testable in implementation.

## Rules: Don't
- Do not allow low-contrast text or hidden focus indicators.
- Do not introduce one-off spacing or typography exceptions.
- Do not use ambiguous labels or non-descriptive actions.
- Do not ship component guidance without explicit state rules.

## Guideline Authoring Workflow
1. Restate design intent in one sentence.
2. Define foundations and semantic tokens.
3. Define component anatomy, variants, interactions, and state behavior.
4. Add accessibility acceptance criteria with pass/fail checks.
5. Add anti-patterns, migration notes, and edge-case handling.
6. End with a QA checklist.

## Required Output Structure
- Context and goals.
- Design tokens and foundations.
- Component-level rules (anatomy, variants, states, responsive behavior).
- Accessibility requirements and testable acceptance criteria.
- Content and tone standards with examples.
- Anti-patterns and prohibited implementations.
- QA checklist.

## Component Rule Expectations
- Include keyboard, pointer, and touch behavior.
- Include spacing and typography token requirements.
- Include long-content, overflow, and empty-state handling.
- Include known page component density: cards (108), links (66), lists (19), buttons (13), navigation (5).


## Quality Gates
- Every non-negotiable rule must use "must".
- Every recommendation should use "should".
- Every accessibility rule must be testable in implementation.
- Teams should prefer system consistency over local visual exceptions.
