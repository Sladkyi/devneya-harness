// Wait for the unchanged suite, including its final report and cleanup.
await import('../tests/acceptance.mjs');

// Windows node-pty can leave ConPTY handles active after the suite returns.
// Drain the runner's logs and return the exit code set by the suite.
await Promise.all([process.stdout, process.stderr].map(stream =>
  new Promise(resolve => stream.write('', resolve))));
process.exit(process.exitCode ?? 0);
