# Deploy Configuration

## Environments

### Local (default)
- **Target**: `./dist/`
- **Port**: 3000
- **Mode**: Development
- **Source Maps**: Enabled

### Staging
- **Target**: Local network share or Docker container
- **Port**: 8080
- **Mode**: Production
- **Source Maps**: Enabled (hidden)

### Production
- **Target**: Self-hosted / local server
- **Port**: 443 (behind reverse proxy)
- **Mode**: Production
- **Source Maps**: Disabled

## Build Thresholds
- **Max Bundle Size**: 500KB (gzipped)
- **Max Load Time**: 2 seconds
- **Min Lighthouse Score**: 90

## Pre-deploy Checklist
- [ ] All tests pass
- [ ] No console.log statements in production code
- [ ] Environment variables are set
- [ ] Database migrations are applied
- [ ] CHANGELOG.md is updated
