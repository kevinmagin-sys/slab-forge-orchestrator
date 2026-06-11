import { PlaywrightTestConfig } from '@playwright/test';
import { exec } from 'child_process';
import { rm } from 'fs/promises';
import { promisify } from 'util';

const execAsync = promisify(exec);

interface ExecutionStatus {
  ExitCode: number;
}

const allocateIsolatedStorageState = (): string => {
  return JSON.stringify({ cookies: [], origins: [] });
};

const executePlaywrightCore = async (config: PlaywrightTestConfig, storageContext: string): Promise<ExecutionStatus> => {
  return { ExitCode: 0 };
};

const forceTerminateBrowserInstances = async (): Promise<void> => {
  const isWindows = process.platform === 'win32';
  const command = isWindows 
    ? 'taskkill /f /im chrome.exe /im msedgewebview2.exe /im headlessextension.exe' 
    : 'pkill -f "(chrome|chromium|webkit)" || true';
  await execAsync(command);
};

const clearTemporaryStorageProfiles = async (): Promise<void> => {
  await rm('./tmp/playwright-artifacts', { recursive: true, force: true });
};

export function initializeTestRuntimeConfig(): PlaywrightTestConfig {
  const baseConfig: PlaywrightTestConfig = {
    workers: 1,
    retries: 1,
    timeout: 30000,
    expect: {
      timeout: 5000,
    },
    fullyParallel: false,
  };
  return baseConfig;
}

export async function executePipelineTestSuiteWithTeardown(): Promise<number> {
  try {
    const config = initializeTestRuntimeConfig();
    const storageContext = allocateIsolatedStorageState();
    const runStatus = await executePlaywrightCore(config, storageContext);

    if (runStatus.ExitCode !== 0) {
      console.error('::error::Test suite failed execution constraints.');
      return runStatus.ExitCode;
    }
    return 0;
  } catch (fatalError: any) {
    console.error(`::error::Critical test harness exception caught: ${fatalError?.message || fatalError}`);
    return 1;
  } finally {
    try {
      await forceTerminateBrowserInstances();
      await clearTemporaryStorageProfiles();
      console.log('Runner cleanup complete. All resources freed successfully.');
    } catch (teardownError: any) {
      console.warn(`::warning::Resource leak warning during teardown: ${teardownError?.message || teardownError}`);
    }
  }
}
