---
name: deploy
description: Auto-loaded workflow for deploying the application locally or to a target environment. Handles build, validation, and deployment steps.
---

# Deploy Skill

## Overview
This skill handles the full deployment pipeline for the Local-First AI Personal Operating System.

## Steps

### 1. Pre-flight Checks
- Verify all tests pass: `npm test`
- Check for linting errors: `npm run lint`
- Ensure no uncommitted changes in git
- Validate environment configuration

### 2. Build
- Run production build: `npm run build`
- Verify build output exists and is valid
- Check bundle size against thresholds

### 3. Deploy
- Read target environment from `deploy-config.md`
- Copy build artifacts to deployment target
- Verify deployment health

### 4. Post-deploy
- Run smoke tests against deployed version
- Report deployment status
- Tag the release in git if successful

## Error Recovery
- If build fails: report errors and abort
- If deploy fails: attempt rollback to previous version
- Always preserve build logs for debugging
