const fs = require('fs');

try {
  const data = fs.readFileSync('test-results/test-results.json', 'utf8');
  const results = JSON.parse(data);

  let passed = 0;
  let failed = 0;
  let skipped = 0;
  let total = 0;

  const areaStatus = {
    'Smoke': 'N/A',
    'Authentication': 'N/A',
    'Knowledge Base': 'N/A',
    'Chat': 'N/A',
    'Retrieval': 'N/A',
    'Network': 'N/A'
  };

  const getArea = (title) => {
    if (title.toLowerCase().includes('smoke')) return 'Smoke';
    if (title.toLowerCase().includes('auth')) return 'Authentication';
    if (title.toLowerCase().includes('knowledge')) return 'Knowledge Base';
    if (title.toLowerCase().includes('chat')) return 'Chat';
    if (title.toLowerCase().includes('retrieval')) return 'Retrieval';
    if (title.toLowerCase().includes('network')) return 'Network';
    return 'Other';
  };

  results.suites.forEach(suite => {
    suite.specs.forEach(spec => {
      total++;
      const area = getArea(suite.title);
      let status = 'PASSED';
      
      const lastRun = spec.tests[0].results[spec.tests[0].results.length - 1];
      if (lastRun.status === 'passed' || lastRun.status === 'expected') {
        passed++;
      } else if (lastRun.status === 'skipped') {
        skipped++;
        status = 'SKIPPED';
      } else {
        failed++;
        status = 'FAILED';
      }
      
      if (areaStatus[area] !== 'FAILED') {
         if (status === 'FAILED') areaStatus[area] = 'FAILED';
         else if (status === 'PASSED') areaStatus[area] = 'PASSED';
      }
    });
  });

  console.log('==================================================');
  console.log('      RAGuard v1.0 E2E Regression Matrix      ');
  console.log('==================================================\n');
  console.log(`Total Tests: ${total}`);
  console.log(`Passed:      ${passed}`);
  console.log(`Failed:      ${failed}`);
  console.log(`Skipped:     ${skipped}\n`);

  console.log('--- Area Status ---');
  Object.keys(areaStatus).forEach(area => {
    let icon = '❓';
    if (areaStatus[area] === 'PASSED') icon = '✅';
    if (areaStatus[area] === 'FAILED') icon = '❌';
    console.log(`${icon} ${area}: ${areaStatus[area]}`);
  });

  console.log('\n==================================================');
  if (failed === 0 && passed > 0) {
    console.log('Overall Status: ✅ PASS');
  } else {
    console.log('Overall Status: ❌ FAIL');
  }

} catch (err) {
  console.error('Could not generate regression matrix. Please run `npm run test:e2e` first.');
}
