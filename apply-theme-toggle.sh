#!/bin/bash

# ============================================
# THEME TOGGLE AUTOMATION SCRIPT
# ============================================
# This script automates the creation and deployment
# of a dark/light theme toggle feature for the CRM

set -e

echo "🎨 Theme Toggle Implementation Script"
echo "======================================"
echo ""

# Step 1: Verify we're in the right directory
if [ ! -d "frontend" ]; then
    echo "❌ Error: frontend directory not found"
    echo "Please run this script from the root CRM directory"
    exit 1
fi

echo "✅ Verified directory structure"
echo ""

# Step 2: Check if git is initialized
if [ ! -d ".git" ]; then
    echo "❌ Error: Not a git repository"
    exit 1
fi

echo "✅ Git repository found"
echo ""

# Step 3: Create feature branch
echo "🌿 Creating feature branch..."
if git rev-parse --verify feat/theme-toggle-dark-light >/dev/null 2>&1; then
    echo "ℹ️  Branch feat/theme-toggle-dark-light already exists"
    git checkout feat/theme-toggle-dark-light
else
    git checkout -b feat/theme-toggle-dark-light
    echo "✅ Created branch: feat/theme-toggle-dark-light"
fi
echo ""

# Step 4: Verify all files are present
echo "📁 Verifying theme files..."
files=(
    "frontend/src/context/ThemeContext.tsx"
    "frontend/src/components/ui/ThemeToggle.tsx"
    "frontend/tailwind.config.ts"
    "frontend/src/app/providers.tsx"
    "frontend/src/components/navigation/MainLayout.tsx"
    "THEME_TOGGLE_FEATURE.md"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ⚠️  Missing: $file"
    fi
done
echo ""

# Step 5: Stage files for commit
echo "📦 Staging files..."
git add \
    frontend/src/context/ThemeContext.tsx \
    frontend/src/components/ui/ThemeToggle.tsx \
    frontend/tailwind.config.ts \
    frontend/src/app/providers.tsx \
    frontend/src/components/navigation/MainLayout.tsx \
    THEME_TOGGLE_FEATURE.md
echo "✅ Files staged"
echo ""

# Step 6: Create commit
echo "💾 Creating commit..."
git commit -m "feat: add dark/light theme toggle

- Create ThemeContext for theme state management
- Implement ThemeToggle UI component with Sun/Moon icons
- Add Tailwind dark mode configuration
- Integrate ThemeProvider in app providers
- Add toggle button to MainLayout header
- Theme preference persists in localStorage
- Supports both dark (default) and light modes
- Smooth transitions between themes"

echo "✅ Commit created"
echo ""

# Step 7: Display next steps
echo "🚀 NEXT STEPS:"
echo "============="
echo ""
echo "1. Test locally:"
echo "   cd frontend && npm run dev"
echo "   Open http://localhost:3000"
echo "   Click the Sun/Moon icon in the top-right header"
echo ""
echo "2. Verify theme persistence:"
echo "   localStorage.getItem('app-theme')  # Should return 'dark' or 'light'"
echo "   Refresh page - theme should persist"
echo ""
echo "3. Push to GitHub:"
echo "   git push origin feat/theme-toggle-dark-light"
echo ""
echo "4. Create Pull Request:"
echo "   Visit: https://github.com/Mu369m/CRM/pull/new/feat/theme-toggle-dark-light"
echo "   Copy description from THEME_TOGGLE_FEATURE.md"
echo ""
echo "5. After review, merge to main:"
echo "   git checkout main"
echo "   git merge feat/theme-toggle-dark-light"
echo "   git push origin main"
echo ""
echo "✨ Theme toggle implementation complete!"
