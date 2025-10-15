#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

/**
 * Sync dependencies from pyproject.toml to config/requirements.txt
 * This ensures that when you run 'uv add xxx', the new dependency
 * gets included in the requirements.txt for npm packaging.
 */

function syncRequirements() {
    try {
        console.log('🔄 Syncing dependencies from pyproject.toml to config/requirements.txt...');

        // Read pyproject.toml
        const pyprojectPath = path.join(__dirname, '..', 'pyproject.toml');
        const pyprojectContent = fs.readFileSync(pyprojectPath, 'utf8');

        // Extract dependencies from [project] section
        const dependencies = [];

        // Find dependencies section
        const dependenciesMatch = pyprojectContent.match(/dependencies\s*=\s*\[([\s\S]*?)\]/);
        if (dependenciesMatch) {
            const depsContent = dependenciesMatch[1];
            const depMatches = depsContent.match(/"([^"]+)"/g);
            if (depMatches) {
                dependencies.push(...depMatches.map(dep => dep.replace(/"/g, '')));
            }
        }

        // Find dev dependencies from [dependency-groups] section
        const devDependenciesMatch = pyprojectContent.match(/dev\s*=\s*\[([\s\S]*?)\]/);
        if (devDependenciesMatch) {
            const devDepsContent = devDependenciesMatch[1];
            const devDepMatches = devDepsContent.match(/"([^"]+)"/g);
            if (devDepMatches) {
                dependencies.push(...devDepMatches.map(dep => dep.replace(/"/g, '')));
            }
        }

        if (dependencies.length === 0) {
            console.log('⚠️  No dependencies found in pyproject.toml');
            return false;
        }

        // Sort dependencies alphabetically
        dependencies.sort();

        // Create requirements content
        const requirementsContent = dependencies.join('\n') + '\n';

        // Write to config/requirements.txt
        const requirementsPath = path.join(__dirname, '..', 'config', 'requirements.txt');

        // Ensure config directory exists
        const configDir = path.dirname(requirementsPath);
        if (!fs.existsSync(configDir)) {
            fs.mkdirSync(configDir, { recursive: true });
        }

        // Check if content would change
        let currentContent = '';
        if (fs.existsSync(requirementsPath)) {
            currentContent = fs.readFileSync(requirementsPath, 'utf8');
        }

        if (currentContent === requirementsContent) {
            console.log('✅ Requirements are already up to date');
            return true;
        }

        // Write new content
        fs.writeFileSync(requirementsPath, requirementsContent);

        console.log(`✅ Updated config/requirements.txt with ${dependencies.length} dependencies:`);
        dependencies.forEach(dep => console.log(`   - ${dep}`));

        return true;

    } catch (error) {
        console.error('❌ Error syncing requirements:', error.message);
        process.exit(1);
    }
}

if (require.main === module) {
    syncRequirements();
}

module.exports = { syncRequirements };