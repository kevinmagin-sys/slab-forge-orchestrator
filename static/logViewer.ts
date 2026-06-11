// ============================================================================
// 1. DATA LAYERS & INTERFACE DEFINITIONS
// ============================================================================
interface ScraperJobResponse {
  JobId: string;
  Status: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'TIMEOUT';
  Data?: any;
}

interface SelectorItem {
  id: string;
  Query: string;
}

interface LocalFormState {
  TargetUrl: string;
  Selectors: SelectorItem[];
  RateLimit: number;
}

// ============================================================================
// 2. LIFECYCLE POLLING ENGINE
// ============================================================================
export function startScraperLifecycle(
  jobId: string, 
  onStateChange: (state: { JobData: ScraperJobResponse | null; IsProcessing: boolean; IsTerminal: boolean; Error: string | null }) => void
) {
  if (!jobId) return;

  const pollInterval = 3000;

  async function checkStatus() {
    try {
      const response = await fetch(`/api/v1/dispatcher/status/${jobId}`);
      
      if (!response.ok) {
        throw new Error(`Network failure: ${response.statusText}`);
      }

      const data: ScraperJobResponse = await response.json();
      const isProcessing = data.Status === 'RUNNING';
      const isTerminal = ['COMPLETED', 'FAILED', 'TIMEOUT'].includes(data.Status);

      onStateChange({
        JobData: data,
        IsProcessing: isProcessing,
        IsTerminal: isTerminal,
        Error: null
      });

      if (isProcessing) {
        setTimeout(checkStatus, pollInterval);
      }

    } catch (err: any) {
      onStateChange({
        JobData: null,
        IsProcessing: false,
        IsTerminal: true,
        Error: err.message || 'Unknown status retrieval error'
      });
    }
  }

  checkStatus();
}

// ============================================================================
// 3. STATE CONTAINER RENDERING MATRIX
// ============================================================================
export function renderGatewayContainer(
  targetId: string, 
  state: { JobData: ScraperJobResponse | null; IsProcessing: boolean; IsTerminal: boolean; Error: string | null }
) {
  const container = document.getElementById(targetId);
  if (!container) return;

  container.className = "w-full max-w-4xl mx-auto rounded-xl border border-slate-200 p-6 transition-all duration-300 ease-in-out bg-white mt-4";

  let currentUiVariant: 'IDLE' | 'ERROR' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'TIMEOUT' = 'IDLE';

  if (state.Error) {
    currentUiVariant = 'ERROR';
  } else if (state.IsProcessing) {
    currentUiVariant = 'PROCESSING';
  } else if (state.IsTerminal && state.JobData) {
    currentUiVariant = state.JobData.Status as any;
  }

  switch (currentUiVariant) {
    case 'PROCESSING':
      container.innerHTML = `
        <div class="relative h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div class="h-full w-full flex-1 bg-indigo-600 transition-all animate-pulse" style="transform: translateX(-30%)"></div>
        </div>
        <div class="space-y-3 mt-4 animate-pulse">
          <div class="h-4 bg-slate-200 rounded w-3/4"></div>
          <div class="h-4 bg-slate-200 rounded w-1/2"></div>
        </div>
      `;
      break;

    case 'COMPLETED':
      container.innerHTML = `
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-sm font-medium text-slate-700">Scrape Results</h3>
        </div>
        <div class="h-[400px] w-full rounded-md border border-slate-100 p-4 overflow-y-auto bg-slate-50">
          <pre class="text-xs text-slate-600 font-mono whitespace-pre-wrap">${JSON.stringify(state.JobData?.Data, null, 2)}</pre>
        </div>
      `;
      break;

    case 'FAILED':
    case 'TIMEOUT':
      container.innerHTML = `
        <div class="rounded-md bg-red-50 p-4 border border-red-200 text-red-700">
          <p class="text-sm font-medium">${state.JobData?.Data?.Message || 'Execution Timeout Exceeded'}</p>
          <button id="retry-execution-btn" class="mt-2 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-md text-sm transition-colors">
            Retry Execution
          </button>
        </div>
      `;
      document.getElementById('retry-execution-btn')?.addEventListener('click', () => {
        window.location.reload();
      });
      break;

    case 'ERROR':
      container.innerHTML = `
        <div class="bg-amber-50 text-amber-800 border border-amber-200 p-3 rounded text-sm">
          A fatal execution hook error has occurred. Please confirm network architecture stability.
        </div>
      `;
      break;

    default:
      container.innerHTML = `
        <div class="text-center py-6 text-slate-400 text-sm">
          No active job execution detected. Enter parameters to start.
        </div>
      `;
      break;
  }
}

// ============================================================================
// 4. PARAMETER CONFIGURATION FORM INTERFACE
// ============================================================================
export function renderScraperConfigurationForm(
  containerId: string, 
  onJobStarted: (jobId: string) => void
) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const state: LocalFormState = {
    TargetUrl: '',
    Selectors: [{ id: '1', Query: '' }],
    RateLimit: 10
  };

  function updateFormUI(errorMessage: string | null = null, isProcessing: boolean = false) {
    container!.innerHTML = `
      <form id="scraper-config-form" class="space-y-4 w-full bg-white p-6 border border-slate-200 rounded-xl">
        ${errorMessage ? `<div class="p-3 text-sm rounded bg-red-50 border border-red-200 text-red-600 font-medium">${errorMessage}</div>` : ''}
        <div class="flex flex-col gap-1.5">
          <label class="text-sm font-medium text-slate-700" for="target-url">Target URL</label>
          <input id="target-url" type="url" value="${state.TargetUrl}" ${isProcessing ? 'disabled' : ''} class="w-full p-2 border rounded border-slate-300 focus:ring-2 focus:ring-indigo-500" placeholder="https://example.com" required />
        </div>
        <div class="flex flex-col gap-2">
          <label class="text-sm font-medium text-slate-700">Target Selectors</label>
          ${state.Selectors.map((selector, index) => `
            <input type="text" id="selector-input-${index}" value="${selector.Query}" ${isProcessing ? 'disabled' : ''} class="p-2 border rounded border-slate-300 focus:ring-2 focus:ring-indigo-500" placeholder="div.product-card > span.price" required />
          `).join('')}
        </div>
        <div class="flex items-center gap-3 mt-6">
          ${isProcessing ? `
            <button type="button" disabled class="w-full bg-slate-400 text-white cursor-not-allowed py-2 px-4 rounded font-medium animate-pulse">Locking Transaction...</button>
          ` : `
            <button type="submit" class="w-full bg-black text-white hover:bg-slate-900 py-2 px-4 rounded font-medium transition-colors">Deploy Scraper Execution Pipeline</button>
          `}
        </div>
      </form>
    `;

    const urlInput = container!.querySelector('#target-url') as HTMLInputElement;
    if (urlInput) {
      urlInput.addEventListener('input', (e) => { 
        state.TargetUrl = (e.target as HTMLInputElement).value; 
      });
    }

    state.Selectors.forEach((_, index) => {
      const selectorInput = container!.querySelector(`#selector-input-${index}`) as HTMLInputElement;
      if (selectorInput) {
        selectorInput.addEventListener('input', (e) => { 
          state.Selectors[index].Query = (e.target as HTMLInputElement).value; 
        });
      }
    });

    // Form submission processing handler
    const form = container!.querySelector('#scraper-config-form') as HTMLFormElement;
    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (isProcessing) return;
      updateFormUI(null, true);

      try {
        const response = await fetch('/api/v1/dispatcher/scrape', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target_url: state.TargetUrl,
            target_selectors: state.Selectors.map(s => s.Query)
          })
        });

        const result = await response.json();
        if (response.ok || response.status === 202) {
          onJobStarted(result.JobId);
        } else {
          updateFormUI(`Backend rejection: ${result.detail || 'Unknown error'}`, false);
        }
      } catch (err: any) {
        updateFormUI(`Submission failed: ${err.message || 'Network error'}`, false);
      }
    });
  }

  updateFormUI();
}