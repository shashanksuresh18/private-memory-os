# Code Style Rules

## General
- Use 2-space indentation for JS/TS/HTML/CSS
- Use 4-space indentation for Python
- Maximum line length: 100 characters
- Always use trailing commas in multi-line structures
- Use single quotes for strings in JavaScript

## Naming Conventions
- **Files**: `kebab-case.js` (e.g., `data-store.js`)
- **Components**: `PascalCase.js` (e.g., `SidePanel.js`)
- **Functions**: `camelCase` (e.g., `fetchUserData`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- **CSS Classes**: `kebab-case` (e.g., `.main-container`)

## JavaScript/TypeScript
- Prefer `const` over `let`; never use `var`
- Use arrow functions for callbacks
- Use template literals over string concatenation
- Destructure objects and arrays when accessing multiple properties
- Always handle promise rejections

## CSS
- Use CSS custom properties (variables) for theming
- Mobile-first responsive design
- Use `rem` for typography, `px` for borders/shadows
- Avoid `!important` unless absolutely necessary

## Comments
- Every exported function must have a JSDoc comment
- Use `// TODO:` for planned improvements
- Use `// HACK:` for temporary workarounds
- Explain *why*, not *what*
